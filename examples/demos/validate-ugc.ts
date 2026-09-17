import type { JudgmentClient } from "@overclock/judgment-core";
import { s, semantic } from "@overclock/semantic-types";
import { z } from "zod";
import { code, pct, table, type DemoReport } from "./types.js";

const Review = z.object({ product: z.string(), stars: z.number().int().min(1).max(5), text: z.string().min(1) });

const reviews = [
  { product: "Trail Runner 3", stars: 5, text: "Light, grippy, and the toe box finally fits wide feet. Two months in, no wear on the outsole." },
  { product: "Trail Runner 3", stars: 1, text: "Garbage. Whoever designed this should be fired and the company sued." },
  { product: "Trail Runner 3", stars: 4, text: "Great shoe. Use code SAVE20 at cheapshoes.example for 20% off, way better than here!" },
  { product: "Trail Runner 3", stars: 3, text: "It's a shoe. It has laces. Fine I guess." },
  { product: "Trail Runner 3", stars: 2, text: "Sole started separating after three weeks of road running. Support replaced it quickly though." },
  { product: "Trail Runner 3", stars: 5, text: "Best. Shoe. Ever. Buy it now, trust me, five stars, amazing, wow." },
];

export async function validateUgc(client: JudgmentClient): Promise<DemoReport> {
  const schema = semantic(
    Review,
    {
      text: [
        s.is("describes actual experience with the product rather than generic praise or hype", { threshold: 0.6 }),
        s.not("is abusive, threatening, or a personal attack", { threshold: 0.3 }),
        s.not("is spam or advertises another seller or discount code", { threshold: 0.3 }),
      ],
      $self: [s.is("the star rating is consistent with the sentiment of the text", { threshold: 0.5 })],
    },
    { client, mode: "review", margin: 0.1 },
  );

  const rows: Array<Array<string | number>> = [];
  for (const review of reviews) {
    const result = await schema.safeParseAsync(review);
    const outcome = !result.success ? "reject" : result.needsReview.length ? "needs review" : "publish";
    const why = !result.success
      ? result.issues.map((i) => i.message.split(" (")[0]).join("; ")
      : result.needsReview.map((e) => `${e.message.split(" (")[0]} (p=${pct(e.p)})`).join("; ") || "—";
    const scores = result.evidence.filter((e) => !e.skipped).map((e) => pct(e.p)).join(" / ");
    rows.push([`${review.stars}★ “${review.text.slice(0, 48)}${review.text.length > 48 ? "…" : ""}”`, outcome, scores, why]);
  }

  return {
    id: "validate-ugc",
    title: "Moderate user-generated content with a review band",
    summary: "Six product reviews are checked for genuine experience, abuse, spam, and rating/text consistency in review mode: clear passes publish, clear failures reject, borderline verdicts go to a human.",
    sections: [
      {
        heading: "The schema",
        body: code(`const schema = semantic(Review, {
  text: [
    s.is("describes actual experience with the product rather than generic praise or hype", { threshold: 0.6 }),
    s.not("is abusive, threatening, or a personal attack", { threshold: 0.3 }),
    s.not("is spam or advertises another seller or discount code", { threshold: 0.3 }),
  ],
  $self: [s.is("the star rating is consistent with the sentiment of the text", { threshold: 0.5 })],
}, { mode: "review", margin: 0.1 });`),
      },
      {
        heading: "Results",
        body: table(["review", "outcome", "p (experience / abusive / spam / consistent)", "reason"], rows),
      },
    ],
  };
}
