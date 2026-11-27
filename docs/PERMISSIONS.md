# Permission matrix (proposed default)
A admin, C collector, V verifier, E editor, P publisher. Permissions additive, object-scope checks mandatory. Admin privileges are explicitly granted and audited, not bypasses of validation.
| Action | A | C | V | E | P |
|---|---|---|---|---|---|
| Manage accounts/roles | yes | no | no | no | no |
| Read catalog | yes | yes | yes | yes | yes |
| Edit catalog | yes | no | no | yes | no |
| Create event draft | yes | yes | yes | yes | no |
| Edit own/assigned draft | yes | yes | yes | yes | no |
| Assign event | yes | no | yes | yes | no |
| Review/verify/return/reject | yes* | no | yes* | yes* | no |
| Cancel/restore occurrence | yes | no | yes | yes | no |
| Manage issue/cover/picks/grid/features | yes | no | no | yes | no |
| Manage recorded fees | yes | no | no | designated only | no |
| Approve issue | designated | no | no | designated | no |
| Publish (later) | designated | no | no | no | designated |
| Upload media | yes | scoped | scoped | yes | no |
| Import commit | yes | designated | no | designated | no |
| Export contacts | designated | no | no | designated | no |
| View audit | designated | no | no | scoped | no |

* Default no self-verification, including administrators. Publisher may see approved snapshot only. Collector reads assigned records and non-sensitive catalog; internal contact access separately granted. Enforce permissions in API services, queryset filtering and every mutation, including bulk actions and workers. Test direct object reference, role revocation, unauthenticated/disabled users, mass assignment and permission escalation. Owner must validate staffing separation before production.
