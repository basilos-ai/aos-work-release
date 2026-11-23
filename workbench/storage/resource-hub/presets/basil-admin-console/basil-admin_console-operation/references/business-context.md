# Product semantics and boundaries

Admin-Console is a governance entry point using existing backend navigation and current-user permissions. This package covers accounts, departments, system roles, resource ACLs, and related helpers from the API documentation. Mentions of models, Credits, resource publishing, or Allowed Models in the overview do not imply undocumented APIs.

- Users belong to departments and SystemRoles. System roles carry system-function permissions and can be TEAM resource ACL subjects. Organization-space Role is a legacy organization permission model; its role IDs are not interchangeable.
- System-menu visibility does not imply resource read/write access. Grants remain subject to current-user system permissions and endpoint business checks. Department endpoints lacking additional system-permission annotations do not authorize changes without user instructions.
- ACL role and department subjects use OR; departments include subdepartment members. Each configuration inherits the nearest explicit folder rule; actions across configurations are unioned. Direct user/department shares and personal ownership may add access. NONE is not a global deny across configurations.
- Administrative `acl_form` returns the complete TEAM configuration tree; employee-visible trees reflect only the current user's scope. A traversable pathShell does not imply all actions.
- Direct sharing accepts only users or departments and supports VIEW/DOWNLOAD/UPLOAD/EDIT. It does not make a department a system administrator or grant MANAGE/SYNC.
- Organization Role endpoints use a backend-fixed shared-organization context; do not switch tenants by guessing tenant-id headers.

Sources: attached "Admin Console User, Role, and Resource Permission API Documentation" (2026-10-27); local PRDs "V1.0.1/Admin Console/15-Admin Console Overview" and "V1.0.2/studio/Department Permission Management PRD" (titles translated). Technical parameters follow the attachment; PRDs are not execution instructions. Some enum JSON excerpts are incomplete (for example, only ASC, FOLDER, or MY/TEAM). This package includes DESC, FILE, and SHARED based on explicit endpoint value descriptions; do not reject valid calls using incomplete excerpts.
