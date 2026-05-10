/**
 * GovGuard™ — Auth0 Post-Login Action
 * 
 * SETUP INSTRUCTIONS:
 * 1. Go to Auth0 Dashboard → Actions → Library → Create Action → Login / Post Login
 * 2. Paste this entire file
 * 3. Click Deploy
 * 4. Go to Actions → Flows → Login → Drag your action into the flow
 * 5. Apply
 */

exports.onExecutePostLogin = async (event, api) => {
  const namespace = "https://govguard.app";
  
  // Get role from user app_metadata (set via Auth0 Management API or manually)
  // Default: compliance_officer for all new users
  const role = event.user.app_metadata?.govguard_role || "compliance_officer";
  
  // Get tenant ID — for single-tenant, use the demo tenant ID
  // For multi-tenant: store tenant_id in app_metadata when provisioning users
  const tenantId = event.user.app_metadata?.govguard_tenant_id || "00000000-0000-0000-0000-000000000001";
  
  // Set custom claims on both ID token and Access token
  api.idToken.setCustomClaim(`${namespace}/role`, role);
  api.idToken.setCustomClaim(`${namespace}/tenant_id`, tenantId);
  api.idToken.setCustomClaim(`${namespace}/user_id`, event.user.user_id);
  
  api.accessToken.setCustomClaim(`${namespace}/role`, role);
  api.accessToken.setCustomClaim(`${namespace}/tenant_id`, tenantId);
  api.accessToken.setCustomClaim(`${namespace}/user_id`, event.user.user_id);
};

// ── ROLES REFERENCE ────────────────────────────────────────────────────────
// To change a user's role:
// 1. Auth0 Dashboard → User Management → Users → Select user → App Metadata
// 2. Set: { "govguard_role": "compliance_officer", "govguard_tenant_id": "your-uuid" }
// 
// Available roles:
//   system_admin       → Full platform access
//   agency_officer     → Cross-grantee oversight
//   compliance_officer → Compliance management, CAP, controls
//   finance_manager    → Approve transactions, view risk scores
//   finance_staff      → Enter transactions, upload invoices
//   auditor            → Read-only, evidence packages
//   equity_analyst     → Equity analytics only
