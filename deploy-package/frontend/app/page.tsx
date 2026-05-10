import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth"; // Import your specific config

export default async function HomePage() {
  // Use the new v4 way to get the session
  const session = await auth0.getSession();

  if (session?.user) {
    redirect("/dashboard");
  } else {
    // If not logged in, redirect to your login page 
    // or directly to auth0 via redirect("/auth/login")
    redirect("/login");
  }
}
