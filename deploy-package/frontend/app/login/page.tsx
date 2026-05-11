import { auth0 } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Shield, Lock, ChevronRight, UserPlus } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  let session = null;
  try {
    session = await auth0.getSession();
  } catch (err) {
    console.error("[auth0] getSession error on /login:", err);
  }
  if (session?.user) redirect("/dashboard");

  return (
    <div className="min-h-screen bg-[#1F3864] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/10 rounded-2xl mb-4">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white tracking-tight">GovGuard™</h1>
          <p className="text-blue-200 mt-2 text-sm">
            Grant Compliance &amp; Fraud Prevention Platform
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Welcome</h2>
          <p className="text-sm text-gray-500 mb-8">
            Sign in to your account or create a new one to get started.
          </p>

          <div className="space-y-3">
            {/* Sign In */}
            <a
              href="/api/auth/login"
              className="w-full flex items-center gap-3 bg-[#1F3864] hover:bg-[#2E75B6] text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 shadow-md hover:shadow-lg group"
            >
              <Lock className="w-5 h-5 shrink-0" />
              <span className="flex-1">Sign In Securely</span>
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </a>

            {/* Sign Up */}
            <a
              href="/api/auth/login?screen_hint=signup"
              className="w-full flex items-center gap-3 border-2 border-[#1F3864] text-[#1F3864] hover:bg-[#1F3864] hover:text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 group"
            >
              <UserPlus className="w-5 h-5 shrink-0" />
              <span className="flex-1">Create Account</span>
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </a>
          </div>

          <div className="mt-6 pt-6 border-t border-gray-100">
            <div className="flex items-center gap-2 justify-center text-xs text-gray-400">
              <Shield className="w-3 h-3" />
              <span>Protected by Auth0 · SOC 2 Type II · GDPR Compliant</span>
            </div>
          </div>
        </div>

        <p className="text-center text-blue-300 text-xs mt-6">
          <a href="/" className="hover:text-white transition-colors">
            ← Back to home
          </a>
        </p>
      </div>
    </div>
  );
}
