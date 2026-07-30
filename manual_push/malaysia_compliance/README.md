# Malaysia compliance rule pack

This operator-managed pack replaces the old, weakly sourced Malaysia seed rows with source-backed rules suitable for automated *screening*. It is not legal advice and does not grant approval to publish.

The Supabase migration `add_ad_policy_rule_evidence_urls` adds the mandatory JSONB provenance column used by this pack. It was applied to the connected project before the pack was seeded.

## Scope

- `source=malaysia`: nationwide online/networked advertising and consumer-protection screening.
- `source=outdoor_dbkl`: physical advertising only within DBKL. It is intentionally not retrieved for general Malaysia online checks. Other locations require the relevant local authority (PBT) rule pack.
- Existing rows remain in Supabase with `source=malaysia_legacy_review_2026` after application. They are retained for audit but excluded from evaluation.

## Sources

- [Malaysian Communications and Multimedia Content Code 2022](https://contentforum.my/wp-content/uploads/2024/01/Content-Code-2022.pdf)
- [KPDN Consumer Protection Act 1999 and guidance index](https://www.kpdn.gov.my/en/public?catid=20%3Ahome&id=187%3Aakta-peraturan-garis-panduan&view=article)
- [KPDN guide to avoiding false or misleading online advertising](https://repositori.kpdn.gov.my/bitstream/123456789/5347/1/Buku%20Garis%20Panduan%20Mengelakkan%20Iklan%20Palsu%20atau%20Mengelirukan%20Dalam%20Talian.pdf)
- [DBKL advertisement-licence FAQ and licensing information](https://www.dbkl.gov.my/jabatan/jabatan-pelesenan-dan-pembangunan-perniagaan)

## Run

```powershell
node manual_push/malaysia_compliance/sync_rule_pack.mjs --dry-run
node manual_push/malaysia_compliance/sync_rule_pack.mjs --apply
```

The script uses `backend/.env`, logs no secret, and mutates only `public.ad_policy_rules` on `--apply`.
