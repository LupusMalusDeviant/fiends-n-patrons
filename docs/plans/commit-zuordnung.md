# Commit-Zuordnung

- **Stand:** 2026-09-15
- **Bezug:** [ADR-0013](../adr/0013-oeffentliche-repos-anonymer-engine-abruf.md) (öffentliche Repos)

Die Historie beider Repos, `fiends-n-patrons` und `grimoire`, wurde bei der Veröffentlichung neu
geschrieben und in die öffentlichen Repos importiert. Dabei haben alle Commits neue IDs bekommen.

- **Die Dokumente in diesem Repo nennen bereits die neuen IDs.** Die Tabellen unten ordnen jeder
  Commit-ID, die in den Dokumenten vorkommt, ihre alte ID zu. Andere Commits sind nicht aufgeführt.
- **Links auf CI-Läufe und Laufnummern aus der Zeit vor der Veröffentlichung** zeigen auf das nicht
  öffentliche Archiv und sind ohne Zugriff darauf nicht erreichbar. Sie bleiben als Nachweis im Text
  stehen; die alten IDs in der Tabelle verbinden sie mit den heutigen Commits.
- **Engine-Tag `v0.1.0`** zeigt auf den neuen Commit `93bed40`, und `Cargo.lock` des Spiels pinnt
  genau diesen Commit. `89e5aa4` in ADR-0009 und im M0-Eintritts-Check ist das Tag-Objekt, kein
  Commit; es entspricht dem Tag im veröffentlichten Engine-Repo.
- **Nicht in der Tabelle:** `6323deb`, `3d96a18` und `e838748` sind Commits fremder GitHub Actions
  (`Swatinem/rust-cache`, `orhun/git-cliff-action`, `webfactory/ssh-agent`) und von der Umschreibung
  nicht betroffen.

IDs sind auf sieben Zeichen gekürzt.

## Zuordnung

### Spiel (`fiends-n-patrons`)

| Alte ID | Neue ID | Erwähnt in |
|---------|---------|------------|
| `2463a4c` | `00d6683` | [0001-phase-p0-fundament.md](0001-phase-p0-fundament.md), [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md), [0002-phase-p1-sichtbarer-kern.md](0002-phase-p1-sichtbarer-kern.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `ec0f153` | `42b10bc` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `0d5ea2c` | `640ab11` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `792c523` | `8642f7d` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |

### Engine (`grimoire`)

| Alte ID | Neue ID | Erwähnt in |
|---------|---------|------------|
| `9c92d78` | `0233c4e` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `d7c66b2` | `0ef7696` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `17198d8` | `30a5981` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `3556d95` | `3fff4c3` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `4efe669` | `44461ce` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `6c61d4c` | `548a30a` | [0002-vertragsfreigabe-wp1.2.md](0002-vertragsfreigabe-wp1.2.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `8e6bbc0` | `5eebd0d` | [0002-vertragsfreigabe-wp1.2.md](0002-vertragsfreigabe-wp1.2.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `c10538e` | `5f3af92` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `ab031bd` | `65e5288` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `b387f8c` | `68a2811` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `ad4ec3d` | `6d07f05` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `b011bed` | `6dcebfb` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `d806f05` | `70a7fb0` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md), [0002-sammelsitzung-a-dossier.md](0002-sammelsitzung-a-dossier.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `5d3ad2f` | `8ca6fff` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `6f21c8c` | `93bed40` | [0009-engine-pin-ueber-git-tag.md](../adr/0009-engine-pin-ueber-git-tag.md), [0001-phase-p0-fundament.md](0001-phase-p0-fundament.md), [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md), [0002-phase-p1-sichtbarer-kern.md](0002-phase-p1-sichtbarer-kern.md) |
| `9b4e49f` | `a9adcaa` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `53acf0b` | `b5ba0fe` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `e5d481a` | `caf1093` | [0002-m0-eintritts-check.md](0002-m0-eintritts-check.md) |
| `2d2cdc2` | `d19860f` | [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `32472d8` | `d5956ed` | [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `d9e54e6` | `f5c9bf5` | [0002-sammelsitzung-a-dossier.md](0002-sammelsitzung-a-dossier.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
| `abfb6ea` | `f9765dd` | [0002-vertragsfreigabe-wp1.2.md](0002-vertragsfreigabe-wp1.2.md), [agentenlauf-2026-09-15.md](agentenlauf-2026-09-15.md) |
