export type Citation = {
  slug: string;
  n: number;
  label: string;
};

// Only allow safe slug characters to prevent XSS via data-slug attribute
const VALID_SLUG_RE = /^[a-zA-Z0-9_\-\/]+$/;

export function extractCitations(text: string): {
  processed: string;
  citations: Citation[];
} {
  const seen = new Map<string, number>();
  const citations: Citation[] = [];

  // Pass 1: collect unique slugs in order of first appearance
  const matchRegex = /【([^】]+)】/g;
  let m: RegExpExecArray | null;
  while ((m = matchRegex.exec(text)) !== null) {
    const slug = m[1];
    if (!VALID_SLUG_RE.test(slug) || seen.has(slug)) continue;

    const n = seen.size + 1;
    seen.set(slug, n);

    // Label = last non-whitespace word before 【
    const before = text.slice(0, m.index);
    const labelMatch = before.match(/(\S+)\s*$/);
    citations.push({ slug, n, label: labelMatch ? labelMatch[1] : slug });
  }

  if (citations.length === 0) {
    return { processed: text, citations: [] };
  }

  // Pass 2: replace each 【slug】 with a superscript HTML marker
  const processed = text.replace(/【([^】]+)】/g, (_, slug: string) => {
    const n = seen.get(slug);
    if (n == null) return `【${slug}】`;
    return `<sup data-slug="${slug}" data-n="${n}">[${n}]</sup>`;
  });

  return { processed, citations };
}
