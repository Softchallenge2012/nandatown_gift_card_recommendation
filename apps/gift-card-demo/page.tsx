"use client";

import { useMemo, useState } from "react";

type GiftCardCatalogItem = {
  card: string;
  merchant: string;
  category: string;
  amountBands: number[];
  keywords: string[];
  notes: string[];
  accent: string;
};

type GiftCardFormState = {
  title: string;
  merchant: string;
  category: string;
  amount: string;
  notes: string;
};

type Recommendation = {
  card: GiftCardCatalogItem;
  score: number;
  reasons: string[];
  suggestedAmount: string;
};

type InputMode = "text" | "decimal" | "numeric" | "tel" | "search" | "email" | "url" | "none";

const giftCardCatalog: GiftCardCatalogItem[] = [
  {
    card: "Amazon",
    merchant: "Amazon",
    category: "shopping",
    amountBands: [25, 50, 100],
    keywords: ["housewarming", "registry", "college", "shipping", "essentials"],
    notes: ["flexible", "broad use", "good fallback"],
    accent: "from-rust via-amber to-cream-50",
  },
  {
    card: "Target",
    merchant: "Target",
    category: "shopping",
    amountBands: [25, 50, 75],
    keywords: ["baby shower", "back to school", "home", "decor", "gift"],
    notes: ["practical", "household", "everyday errands"],
    accent: "from-ink-900 via-ink-700 to-ink-500",
  },
  {
    card: "Steam",
    merchant: "Steam",
    category: "gaming",
    amountBands: [20, 50, 100],
    keywords: ["gaming", "pc", "tournament", "teen", "birthday"],
    notes: ["digital", "instant delivery", "player friendly"],
    accent: "from-rust-light via-rust to-ink-900",
  },
  {
    card: "Nintendo",
    merchant: "Nintendo",
    category: "gaming",
    amountBands: [20, 35, 50],
    keywords: ["switch", "family", "party", "gaming", "kids"],
    notes: ["family-friendly", "console", "easy pick"],
    accent: "from-sage via-amber to-rust-light",
  },
  {
    card: "Starbucks",
    merchant: "Starbucks",
    category: "coffee",
    amountBands: [15, 25, 50],
    keywords: ["teacher", "coworker", "morning", "commute", "thanks"],
    notes: ["small treat", "daily ritual", "easy thank-you"],
    accent: "from-ink-700 via-rust-light to-amber",
  },
  {
    card: "Sephora",
    merchant: "Sephora",
    category: "beauty",
    amountBands: [25, 50, 75],
    keywords: ["birthday", "beauty", "self-care", "fashion", "night out"],
    notes: ["premium feel", "beauty discovery", "special occasion"],
    accent: "from-amber via-rust-light to-cream-50",
  },
  {
    card: "Apple",
    merchant: "Apple",
    category: "electronics",
    amountBands: [25, 50, 100],
    keywords: ["creator", "student", "upgrade", "music", "app store"],
    notes: ["digital services", "hardware-friendly", "polished"],
    accent: "from-ink-900 via-sage to-cream-50",
  },
  {
    card: "DoorDash",
    merchant: "DoorDash",
    category: "food",
    amountBands: [20, 35, 60],
    keywords: ["late night", "busy week", "new parent", "team lunch", "delivery"],
    notes: ["fast relief", "meal support", "convenience"],
    accent: "from-rust via-amber to-sage",
  },
];

const quickPresets: Array<Pick<GiftCardFormState, "title" | "merchant" | "category" | "amount" | "notes">> = [
  {
    title: "Birthday for a teen gamer",
    merchant: "",
    category: "gaming",
    amount: "50",
    notes: "likes PC games and instant delivery",
  },
  {
    title: "Teacher thank-you",
    merchant: "",
    category: "coffee",
    amount: "25",
    notes: "small appreciative gift for mornings",
  },
  {
    title: "New apartment housewarming",
    merchant: "",
    category: "shopping",
    amount: "75",
    notes: "needs flexible essentials and decor",
  },
];

const categoryOptions = [
  "gaming",
  "coffee",
  "shopping",
  "beauty",
  "food",
  "electronics",
  "general",
];

const initialForm: GiftCardFormState = {
  title: "Birthday for a teen gamer",
  merchant: "",
  category: "gaming",
  amount: "50",
  notes: "likes PC games and instant delivery",
};

function normalize(value: string): string {
  return value.toLowerCase().trim();
}

function tokenize(value: string): string[] {
  return normalize(value)
    .split(/[^a-z0-9]+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function amountTarget(value: string): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function nearestBandAmount(target: number, band: number[]): number {
  if (band.length === 0) return 0;
  return band.reduce((best, candidate) => {
    const bestDistance = Math.abs(best - target);
    const candidateDistance = Math.abs(candidate - target);
    return candidateDistance < bestDistance ? candidate : best;
  }, band[0]);
}

function amountFit(target: number, band: number[]): number {
  if (target <= 0 || band.length === 0) return 0.5;
  const nearest = nearestBandAmount(target, band);
  const delta = Math.abs(nearest - target);
  return Math.max(0, 1 - delta / Math.max(target, nearest, 1));
}

function scoreRecommendation(
  card: GiftCardCatalogItem,
  form: GiftCardFormState,
): Recommendation {
  const merchant = normalize(form.merchant);
  const category = normalize(form.category);
  const noteTokens = tokenize(form.notes);
  const titleTokens = tokenize(form.title);
  const searchSpace = [card.card, card.merchant, card.category, ...card.keywords, ...card.notes]
    .join(" ")
    .toLowerCase();
  const matchedTokens = [...titleTokens, ...noteTokens].filter((token) => searchSpace.includes(token));
  const merchantMatch = merchant.length > 0 && normalize(card.merchant).includes(merchant);
  const categoryMatch = category.length > 0 && normalize(card.category).includes(category);
  const amount = amountTarget(form.amount);
  const fit = amountFit(amount, card.amountBands);
  const nearestAmount = amount > 0 ? nearestBandAmount(amount, card.amountBands) : card.amountBands[0];

  const score =
    matchedTokens.length * 18 +
    (merchantMatch ? 30 : 0) +
    (categoryMatch ? 24 : 0) +
    fit * 26 +
    (card.keywords.some((keyword) => searchSpace.includes(keyword)) ? 8 : 0);

  const reasons = [
    merchantMatch ? `${card.merchant} matches the merchant` : null,
    categoryMatch ? `${card.category} fits the selected category` : null,
    matchedTokens.length > 0 ? `shares ${matchedTokens.slice(0, 3).join(", ")}` : null,
    amount > 0 ? `amount lands near $${nearestAmount}` : null,
  ].filter(Boolean) as string[];

  return {
    card,
    score,
    reasons: reasons.length > 0 ? reasons : ["Broad fallback for this gift intent"],
    suggestedAmount: amount > 0 ? `$${nearestAmount}` : `$${card.amountBands[0]}`,
  };
}

function recommendationsForForm(form: GiftCardFormState): Recommendation[] {
  return giftCardCatalog
    .map((card) => scoreRecommendation(card, form))
    .sort((a, b) => b.score - a.score || a.card.card.localeCompare(b.card.card))
    .slice(0, 4);
}

function progressLabel(score: number): string {
  if (score >= 90) return "Perfect fit";
  if (score >= 65) return "Strong match";
  if (score >= 40) return "Good fallback";
  return "Broad match";
}

export default function GiftCardRecommendationDemoPage() {
  const [form, setForm] = useState<GiftCardFormState>(initialForm);

  const recommendations = useMemo(() => recommendationsForForm(form), [form]);
  const dominantRecommendation = recommendations[0];
  const amountValue = amountTarget(form.amount);

  return (
    <div className="relative min-h-screen overflow-hidden bg-cream-100 px-4 py-6 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-rust/10 blur-3xl" />
        <div className="absolute right-[-6rem] top-44 h-72 w-72 rounded-full bg-ink-300/15 blur-3xl" />
        <div className="absolute bottom-[-5rem] left-[-2rem] h-72 w-72 rounded-full bg-sage/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-[430px] items-center justify-center">
        <div className="w-full rounded-[2.25rem] border border-cream-400/80 bg-ink-900 p-2 shadow-[0_28px_80px_rgba(20,19,18,0.22)]">
          <div className="rounded-[1.9rem] bg-cream-100">
            <div className="flex items-center justify-between px-6 pb-3 pt-4 text-[0.7rem] font-medium text-ink-400">
              <span>9:41</span>
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-ink-400" />
                <span className="h-1.5 w-1.5 rounded-full bg-ink-400/70" />
                <span className="h-1.5 w-4 rounded-full bg-ink-400" />
              </div>
            </div>

            <main className="space-y-4 px-4 pb-4">
              <header className="animate-fade-in rounded-[1.75rem] border border-cream-400/80 bg-gradient-to-br from-ink-900 via-ink-800 to-ink-700 px-4 py-5 text-cream-50 shadow-[0_16px_36px_rgba(20,19,18,0.18)]">
                <div className="flex items-center justify-between">
                  <span className="eyebrow text-cream-200">Mobile react</span>
                  <span className="rounded-full border border-cream-50/20 bg-cream-50/10 px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-cream-50/85">
                    live scorer
                  </span>
                </div>
                <h1 className="mt-4 font-display text-[2.1rem] leading-[0.95] tracking-[-0.03em]">
                  Gift card
                  <br />
                  recommender
                </h1>
                <p className="mt-3 max-w-[27ch] text-[0.95rem] leading-[1.5] text-cream-50/82">
                  Enter the gift card title, merchant, category, amount, and notes.
                  The app ranks the best fit and explains why.
                </p>
              </header>

              <section className="animate-slide-up stagger-1 rounded-[1.6rem] border border-cream-400/80 bg-cream-50 p-4 shadow-[0_10px_28px_rgba(20,19,18,0.08)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="eyebrow">Gift details</p>
                    <h2 className="mt-1 font-display text-[1.35rem] text-ink-900">
                      What are you recommending for?
                    </h2>
                  </div>
                  <span className="rounded-full border border-rust/20 bg-rust/10 px-3 py-1 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-rust">
                    {progressLabel(dominantRecommendation.score)}
                  </span>
                </div>

                <div className="mt-4 space-y-3.5">
                  <Field
                    id="gift-title"
                    label="Gift card title"
                    value={form.title}
                    placeholder="Birthday for a teen gamer"
                    onChange={(value) => setForm((current) => ({ ...current, title: value }))}
                  />
                  <Field
                    id="merchant"
                    label="Merchant"
                    value={form.merchant}
                    placeholder="Steam, Sephora, Target..."
                    onChange={(value) => setForm((current) => ({ ...current, merchant: value }))}
                  />

                  <div>
                    <label className="eyebrow" htmlFor="category">
                      Category
                    </label>
                    <select
                      id="category"
                      value={form.category}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, category: event.target.value }))
                      }
                      className="mt-2 w-full rounded-2xl border border-cream-400 bg-cream-100 px-4 py-3 text-[0.95rem] text-ink-800 outline-none transition-colors focus:border-ink-300"
                    >
                      {categoryOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>

                  <Field
                    id="amount"
                    label="Amount"
                    value={form.amount}
                    placeholder="50"
                    inputMode="decimal"
                    onChange={(value) => setForm((current) => ({ ...current, amount: value }))}
                  />

                  <div>
                    <label className="eyebrow" htmlFor="notes">
                      Notes
                    </label>
                    <textarea
                      id="notes"
                      rows={3}
                      value={form.notes}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, notes: event.target.value }))
                      }
                      placeholder="Any special context, recipient taste, or occasion"
                      className="mt-2 w-full resize-none rounded-2xl border border-cream-400 bg-cream-100 px-4 py-3 text-[0.95rem] text-ink-800 outline-none transition-colors placeholder:text-ink-300 focus:border-ink-300"
                    />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {quickPresets.map((preset) => (
                    <button
                      key={preset.title}
                      type="button"
                      onClick={() => setForm(preset)}
                      className="rounded-full border border-cream-400 bg-cream-100 px-3 py-2 text-[0.74rem] font-medium text-ink-600 transition-colors hover:border-ink-300 hover:text-ink-900"
                    >
                      {preset.title}
                    </button>
                  ))}
                </div>
              </section>

              <section className="animate-slide-up stagger-2 rounded-[1.6rem] border border-ink-900/10 bg-gradient-to-br from-ink-900 via-ink-800 to-ink-700 p-4 text-cream-50 shadow-[0_16px_36px_rgba(20,19,18,0.2)]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="eyebrow text-cream-200">Top recommendation</p>
                    <h2 className="mt-1 font-display text-[1.4rem] leading-tight">
                      {dominantRecommendation.card.card}
                    </h2>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-cream-50/70">
                      score
                    </p>
                    <p className="mt-1 text-[1.5rem] font-semibold leading-none">
                      {Math.round(dominantRecommendation.score)}
                    </p>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3">
                  <MetricCard label="Suggested amount" value={dominantRecommendation.suggestedAmount} />
                  <MetricCard label="Match level" value={progressLabel(dominantRecommendation.score)} />
                </div>

                <div className="mt-4 rounded-[1.3rem] border border-cream-50/15 bg-cream-50/8 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-[0.95rem]">Why this fits</p>
                      <p className="mt-1 text-[0.82rem] leading-[1.45] text-cream-50/74">
                        {dominantRecommendation.reasons[0]}
                      </p>
                    </div>
                    <div className={`h-12 w-12 rounded-2xl bg-gradient-to-br ${dominantRecommendation.card.accent}`} />
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {[dominantRecommendation.card.category, dominantRecommendation.card.merchant, ...dominantRecommendation.card.notes]
                      .slice(0, 4)
                      .map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-cream-50/15 bg-cream-50/8 px-2.5 py-1 font-mono text-[0.61rem] uppercase tracking-[0.16em] text-cream-50/76"
                        >
                          {tag}
                        </span>
                      ))}
                  </div>
                </div>
              </section>

              <section className="animate-slide-up stagger-3 rounded-[1.6rem] border border-cream-400/80 bg-cream-50 p-4 shadow-[0_10px_28px_rgba(20,19,18,0.08)]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="eyebrow">Ranked cards</p>
                    <h2 className="mt-1 font-display text-[1.3rem] text-ink-900">Best options</h2>
                  </div>
                  <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-400">
                    {recommendations.length} results
                  </span>
                </div>

                <div className="mt-4 space-y-3">
                  {recommendations.map((item, index) => (
                    <article
                      key={item.card.card}
                      className="rounded-[1.35rem] border border-cream-400 bg-cream-100 p-3.5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-[1rem] font-semibold text-ink-900">
                            {item.card.card}
                          </p>
                          <p className="mt-0.5 text-[0.8rem] text-ink-500">
                            {item.card.category} · {item.card.merchant}
                          </p>
                        </div>
                        <span className="rounded-full border border-cream-400 bg-cream-50 px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-500">
                          #{index + 1}
                        </span>
                      </div>

                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <MetricCard light label="Score" value={Math.round(item.score).toString()} />
                        <MetricCard light label="Amount" value={item.suggestedAmount} />
                      </div>

                      <p className="mt-3 text-[0.84rem] leading-[1.45] text-ink-600">
                        {item.reasons.join(" · ")}
                      </p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="animate-slide-up stagger-4 rounded-[1.6rem] border border-cream-400/80 bg-cream-50 p-4 shadow-[0_10px_28px_rgba(20,19,18,0.08)]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="eyebrow">Input summary</p>
                    <h2 className="mt-1 font-display text-[1.3rem] text-ink-900">What the model sees</h2>
                  </div>
                  <span className="font-mono text-[0.62rem] uppercase tracking-[0.18em] text-ink-400">
                    {amountValue > 0 ? `$${amountValue.toFixed(0)}` : "no amount"}
                  </span>
                </div>

                <div className="mt-4 space-y-2.5">
                  <SummaryRow label="Title" value={form.title} />
                  <SummaryRow label="Merchant" value={form.merchant || "Not specified"} />
                  <SummaryRow label="Category" value={form.category} />
                  <SummaryRow label="Amount" value={form.amount ? `$${form.amount}` : "Not specified"} />
                  <SummaryRow label="Notes" value={form.notes || "No notes"} />
                </div>
              </section>
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({
  id,
  label,
  value,
  placeholder,
  onChange,
  inputMode = "text",
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
  inputMode?: InputMode;
}) {
  return (
    <div>
      <label className="eyebrow" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        inputMode={inputMode}
        className="mt-2 w-full rounded-2xl border border-cream-400 bg-cream-100 px-4 py-3 text-[0.95rem] text-ink-800 outline-none transition-colors placeholder:text-ink-300 focus:border-ink-300"
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
  light = false,
}: {
  label: string;
  value: string;
  light?: boolean;
}) {
  return (
    <div className={`rounded-2xl border px-3 py-2.5 ${light ? "border-cream-400 bg-cream-50" : "border-cream-50/15 bg-cream-50/8"}`}>
      <p className={`font-mono text-[0.58rem] uppercase tracking-[0.16em] ${light ? "text-ink-400" : "text-cream-50/70"}`}>
        {label}
      </p>
      <p className={`mt-1 text-[0.95rem] font-semibold ${light ? "text-ink-900" : "text-cream-50"}`}>
        {value}
      </p>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-2xl border border-cream-400 bg-cream-100 px-3 py-2.5">
      <span className="font-mono text-[0.62rem] uppercase tracking-[0.16em] text-ink-400">
        {label}
      </span>
      <span className="max-w-[65%] text-right text-[0.82rem] leading-[1.4] text-ink-700">
        {value}
      </span>
    </div>
  );
}
