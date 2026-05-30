"use client";

import { useI18n } from "./LanguageProvider";

type PageHeaderProps = {
  title: string;
  description: string;
  eyebrow?: string;
  titleEn?: string;
  descriptionEn?: string;
  eyebrowEn?: string;
};

export function PageHeader({
  title,
  description,
  eyebrow,
  titleEn,
  descriptionEn,
  eyebrowEn,
}: PageHeaderProps) {
  const { text } = useI18n();

  return (
    <section className="mb-8 max-w-3xl">
      {eyebrow ? (
        <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-jade">{text(eyebrow, eyebrowEn)}</p>
      ) : null}
      <h1 className="text-3xl font-semibold tracking-normal text-ink sm:text-4xl">{text(title, titleEn)}</h1>
      <p className="mt-4 text-base leading-7 text-slate-600">{text(description, descriptionEn)}</p>
    </section>
  );
}
