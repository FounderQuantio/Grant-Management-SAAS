import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let session = null;
  try {
    session = await auth0.getSession();
  } catch (err) {
    console.error("[auth0] getSession error on /:", err);
  }
  if (session?.user) redirect("/dashboard");
  redirect("/login");
}
