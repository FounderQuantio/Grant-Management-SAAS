import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth";

export default async function HomePage() {
  try {
    const session = await auth0.getSession();
    if (session?.user) redirect("/dashboard");
  } catch (err) {
    console.error("[auth0] getSession error on /:", err);
  }
  redirect("/login");
}
