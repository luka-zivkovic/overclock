import type { JudgmentClient } from "@overclock/judgment-core";
import { s, semantic } from "@overclock/semantic-types";
import { z } from "zod";
import { code, pct, table, type DemoReport } from "./types.js";

const ReplyShape = z.object({ subject: z.string(), body: z.string() });

const spec = {
  body: [
    s.is("is polite and professional", { threshold: 0.8 }),
    s.not("contains personally identifiable information such as a full card number, password, or home address", { threshold: 0.2 }),
    s.oneOf("primary intent", { answer: null, escalate: null, decline: null }, { expect: ["answer", "escalate"] }),
    s.rated("clarity", ["confusing", "acceptable", "crystal clear"], { min: 1 }),
  ],
  $self: [s.is("the subject line matches what the body says")],
};

const candidates = [
  {
    label: "good",
    subject: "Your refund is on its way",
    body: "Thanks for flagging the double charge. I've refunded the duplicate payment; it will show on your statement within 3 business days. Reply here if it doesn't.",
  },
  {
    label: "rude",
    subject: "Refund",
    body: "As I already said, refunds take time. Read the policy before emailing again.",
  },
  {
    label: "leaks data",
    subject: "Your refund is on its way",
    body: "Refunded to card 4111 1111 1111 1111 (exp 04/28) for John Q. Public, 12 Elm St. You'll see it in 3 days.",
  },
  {
    label: "mismatched subject",
    subject: "Welcome to the newsletter",
    body: "Sorry, we can't refund this order because it was delivered and signed for on 4 March. I'm happy to help with a replacement instead.",
  },
];

export async function guardLlmOutput(client: JudgmentClient): Promise<DemoReport> {
  const Reply = semantic(ReplyShape, spec, { client });
  const rows: Array<Array<string | number>> = [];
  const details: string[] = [];
  for (const candidate of candidates) {
    const result = await Reply.safeParseAsync({ subject: candidate.subject, body: candidate.body });
    const failed = result.success ? [] : result.issues.map((issue) => `${issue.path.join(".") || "$self"}: ${issue.message}`);
    rows.push([candidate.label, result.success ? "accepted" : "rejected", failed.length ? failed.join("<br>") : "—"]);
    details.push(
      `**${candidate.label}** (${result.success ? "accepted" : "rejected"})\n\n` +
        table(
          ["check", "p", "verdict"],
          result.evidence.map((e) => [`${e.path.join(".") || "$self"} · ${e.message.split(" (")[0]}`, pct(e.p), e.pass ? "pass" : "fail"]),
        ),
    );
  }
  return {
    id: "guard-llm-output",
    title: "Guard LLM output before it ships",
    summary: "Four drafted support replies go through one semantic schema. Each draft costs one request, however many predicates it declares.",
    sections: [
      {
        heading: "The schema",
        body: code(`const Reply = semantic(
  z.object({ subject: z.string(), body: z.string() }),
  {
    body: [
      s.is("is polite and professional", { threshold: 0.8 }),
      s.not("contains personally identifiable information…", { threshold: 0.2 }),
      s.oneOf("primary intent", { answer: null, escalate: null, decline: null }, { expect: ["answer", "escalate"] }),
      s.rated("clarity", ["confusing", "acceptable", "crystal clear"], { min: 1 }),
    ],
    $self: [s.is("the subject line matches what the body says")],
  },
);
const result = await Reply.safeParseAsync(draft);`),
      },
      { heading: "Results", body: table(["draft", "outcome", "failed checks"], rows) },
      { heading: "Evidence per draft", body: details.join("\n\n") },
    ],
  };
}
