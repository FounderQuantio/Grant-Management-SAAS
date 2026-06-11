import { Shield, ChevronRight } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-[#1F3864] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/10 rounded-2xl mb-4">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white tracking-tight">GovGuard™</h1>
          <p className="text-blue-200 mt-2 text-sm">
            Grant Compliance &amp; Fraud Prevention Platform
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Welcome</h2>
          <p className="text-sm text-gray-500 mb-8">
            Explore the GovGuard™ demo platform.
          </p>

          <Link
            href="/dashboard"
            className="w-full flex items-center gap-3 bg-[#1F3864] hover:bg-[#2E75B6] text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 shadow-md hover:shadow-lg group"
          >
            <Shield className="w-5 h-5 shrink-0" />
            <span className="flex-1">Enter GovGuard™</span>
            <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Link>

          <div className="mt-6 pt-6 border-t border-gray-100">
            <div className="flex items-center gap-2 justify-center text-xs text-gray-400">
              <Shield className="w-3 h-3" />
              <span>SOC 2 Type II · FedRAMP-aligned · Demo Mode</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
