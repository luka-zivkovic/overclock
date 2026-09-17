import type { JudgmentClient } from "@overclock/judgment-core";
import { ContractViolation, guarded, meaning, s } from "@overclock/semantic-types";
import { code, pct, table, type DemoReport } from "./types.js";

/** A deliberately naive summarizer: it keeps the first sentence. Sometimes that is the point, sometimes not. */
function firstSentence(text: string): string {
  const match = /^(.*?[.!?])(\s|$)/.exec(text.trim());
  return match ? match[1]! : text.trim();
}

const inputs = [
  "Our Q3 revenue grew 14% year over year, driven by the enterprise tier. Churn fell to 2.1%. We plan to hire twelve engineers in Q4.",
  "Hello there. Anyway, the important thing is that the migration to Postgres 17 finished on Tuesday with zero data loss and 40% faster p95 latency.",
  "Reminder: the office is closed on Monday. Also, the new expense policy caps meals at $40 per day and requires receipts for anything above $10.",
];

export async function contracts(client: JudgmentClient): Promise<DemoReport> {
  const summarize = guarded(async (text: string) => firstSentence(text), {
    post: [s.is("the output is a faithful summary of the most important information in the input", { threshold: 0.6 })],
    client,
  });

  const rows: Array<Array<string | number>> = [];
  for (const input of inputs) {
    try {
      const output = await summarize(input);
      rows.push([input.slice(0, 60) + "…", `“${output}”`, "accepted", "—"]);
    } catch (error) {
      if (!(error instanceof ContractViolation)) throw error;
      const evidence = error.evidence[0]!;
      rows.push([input.slice(0, 60) + "…", `“${firstSentence(input)}”`, "post-condition failed", `p=${pct(evidence.p)}`]);
    }
  }

  // A property expressed as a probability: sampled inputs, not a proof.
  const samples = ["refund", "cancel my subscription", "how do I export my data", "the app crashes on launch", "thanks, all sorted"];
  const propertyRows: Array<Array<string | number>> = [];
  for (const sample of samples) {
    const reply = `We received your message about "${sample}". A specialist will reply within one business day.`;
    const p = await meaning({ customer: sample, reply }, "the reply acknowledges the customer's specific topic", { client });
    propertyRows.push([sample, pct(p), p > 0.7 ? "holds" : "violated"]);
  }

  return {
    id: "contracts",
    title: "Semantic contracts on function boundaries",
    summary: "A naive summarizer is wrapped with a post-condition. Where the first sentence is the important one the contract holds; where it is filler, the contract catches it. A second block checks a property over sampled inputs.",
    sections: [
      {
        heading: "The contract",
        body: code(`const summarize = guarded(async (text: string) => firstSentence(text), {
  post: [s.is("the output is a faithful summary of the most important information in the input", { threshold: 0.6 })],
});
await summarize(text); // throws ContractViolation with evidence when the post-condition fails`),
      },
      { heading: "Results", body: table(["input", "output", "outcome", "evidence"], rows) },
      {
        heading: "Property over samples",
        body:
          code(`for (const sample of samples) {
  const p = await meaning({ customer: sample, reply: autoReply(sample) }, "the reply acknowledges the customer's specific topic");
  // fast-check version: fc.assert(fc.asyncProperty(arbTopic, async (t) => (await meaning(...)) > 0.7))
}`) +
          "\n\n" +
          table(["customer message", "p", "property"], propertyRows),
      },
    ],
  };
}
