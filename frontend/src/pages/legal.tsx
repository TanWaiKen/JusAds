import { Link, useLocation } from "react-router";

const CONTENT = {
  terms: {
    title: "Terms of Service",
    intro: "These terms explain the basic rules for using JusAds.",
    sections: [
      ["Using JusAds", "Use JusAds only for lawful advertising and only with content you have permission to use."],
      ["Your responsibility", "You are responsible for reviewing every generated ad before publishing it and for confirming that it meets your business and legal requirements."],
      ["Service changes", "Features and limits may change as JusAds improves. Material changes will be communicated through the product or your registered email."],
    ],
  },
  privacy: {
    title: "Privacy Policy",
    intro: "This policy explains, in plain language, how JusAds handles your information.",
    sections: [
      ["Information we use", "JusAds uses your account details and the content you upload to provide the service."],
      ["How it is used", "Your information is used to create and save ads, provide support, protect the service, and improve product reliability."],
      ["Your choices", "You can ask about, correct, or request deletion of your account information by contacting hello@jusads.com."],
    ],
  },
} as const;

export default function LegalPage() {
  const { pathname } = useLocation();
  const page = pathname === "/privacy" ? CONTENT.privacy : CONTENT.terms;

  return (
    <main className="min-h-svh bg-background px-6 py-12 text-text-body">
      <article className="mx-auto max-w-[760px]">
        <Link to="/" className="inline-flex min-h-11 items-center font-semibold text-blue-700 hover:underline dark:text-blue-300">Back to JusAds</Link>
        <h1 className="mt-8 text-4xl font-semibold tracking-tight text-text-heading">{page.title}</h1>
        <p className="mt-4 text-lg leading-relaxed">{page.intro}</p>
        <p className="mt-2 text-sm text-text-caption">Last updated: 24 July 2026</p>
        <div className="mt-10 space-y-8">
          {page.sections.map(([title, body]) => (
            <section key={title}>
              <h2 className="text-2xl font-semibold text-text-heading">{title}</h2>
              <p className="mt-3 leading-relaxed">{body}</p>
            </section>
          ))}
        </div>
      </article>
    </main>
  );
}
