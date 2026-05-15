import {
  Shield,
  CheckCircle,
  Lock,
  BarChart3,
  FileSearch,
  AlertTriangle,
  ChevronRight,
  UserPlus,
} from "lucide-react";

const features = [
  {
    icon: Shield,
    title: "Grant Compliance",
    description:
      "Real-time monitoring against 2 CFR 200 standards with automated control testing and evidence tracking.",
  },
  {
    icon: AlertTriangle,
    title: "Fraud Prevention",
    description:
      "ML-powered transaction screening flags anomalies and duplicate invoices before funds are disbursed.",
  },
  {
    icon: FileSearch,
    title: "Audit Readiness",
    description:
      "Maintain a complete evidence trail and corrective action plans for every finding — always exam-ready.",
  },
  {
    icon: BarChart3,
    title: "Risk Intelligence",
    description:
      "Live dashboards with KPIs, risk leaderboards, and exception workflows across all your grants.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-[#1F3864] flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 max-w-6xl mx-auto w-full">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-white/15 rounded-lg flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <span className="text-white text-xl font-bold tracking-tight">GovGuard™</span>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/login"
            className="text-blue-200 hover:text-white text-sm font-medium transition-colors px-4 py-2"
          >
            Sign In
          </a>
          <a
            href="/api/auth/login?screen_hint=signup"
            className="bg-white text-[#1F3864] hover:bg-blue-50 text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors shadow-sm"
          >
            Get Started
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex-1 max-w-6xl mx-auto w-full px-8 pt-16 pb-20 flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 bg-white/10 text-blue-200 text-xs font-medium px-3.5 py-1.5 rounded-full mb-8">
          <CheckCircle className="w-3.5 h-3.5" />
          FedRAMP-aligned · SOC 2 Type II · GDPR Compliant
        </div>

        <h1 className="text-5xl font-bold text-white leading-tight mb-5 max-w-2xl">
          Federal Grant Compliance &amp; Fraud Prevention
        </h1>

        <p className="text-blue-200 text-lg max-w-xl mx-auto mb-10 leading-relaxed">
          GovGuard™ gives grant administrators and compliance officers real-time
          visibility, automated controls, and audit-ready documentation — all in
          one platform.
        </p>

        <div className="flex items-center justify-center gap-4 flex-wrap">
          <a
            href="/api/auth/login?screen_hint=signup"
            className="flex items-center gap-2 bg-white text-[#1F3864] hover:bg-blue-50 font-semibold px-7 py-3.5 rounded-xl transition-all shadow-lg hover:shadow-xl group"
          >
            <UserPlus className="w-4 h-4" />
            Start Free Trial
            <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
          </a>
          <a
            href="/api/auth/login"
            className="flex items-center gap-2 border-2 border-white/30 hover:border-white/60 text-white font-semibold px-7 py-3.5 rounded-xl transition-all"
          >
            <Lock className="w-4 h-4" />
            Sign In
          </a>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-20 w-full">
          {features.map(({ icon: Icon, title, description }) => (
            <div
              key={title}
              className="bg-white/10 hover:bg-white/15 backdrop-blur rounded-2xl p-6 text-left transition-colors"
            >
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-4">
                <Icon className="w-5 h-5 text-white" />
              </div>
              <h3 className="text-white font-semibold mb-2">{title}</h3>
              <p className="text-blue-200 text-sm leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-7">
        <p className="text-center text-blue-300/70 text-sm">
          © {new Date().getFullYear()} GovGuard™ · Built for federal grant administrators.
        </p>
      </footer>
    </div>
  );
}
