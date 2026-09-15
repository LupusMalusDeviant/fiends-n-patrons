# ADR-0012: Lizenz beider Repos — Alle Rechte vorbehalten

- **Status:** Akzeptiert (PO-Entscheidung vom 2026-09-15); schließt P0-Rest R-09. 0010 und 0011 sind Vorschläge mit vorläufigen Nummern, 0012 ist die nächste freie Nummer.
- **Datum:** 2026-09-15
- **Entscheider:** Lupus Malus Deviant (PO), vorbereitet durch Claude
- **Bezug:** [Plan 0001](../plans/0001-phase-p0-fundament.md) (WP1.4, Umsetzungsstand WP1), [M0-Eintritts-Check](../plans/0002-m0-eintritts-check.md) (R-09), [PRD-0000](../prd/0000-index-fiends-n-patrons.md) (E17), [PRD-0001](../prd/0001-vision-und-scope.md), [PRD-0017](../prd/0017-plattform-ci-distribution.md), [ADR-0002](0002-engine-eigenes-repo.md), [ADR-0009](0009-engine-pin-ueber-git-tag.md), [ADR-0013](0013-oeffentliche-repos-anonymer-engine-abruf.md) (Veröffentlichung, anonymer Engine-Abruf); Engine-Repo `grimoire`: Engine-ADR-0009 „Lizenz der Engine — Alle Rechte vorbehalten“ (Nummer vorläufig)

## Kontext

Plan 0001 verlangt in WP1.4 einen dokumentierten Lizenzentscheid und nennt als Empfehlung
„privat/All rights reserved“. Der Umsetzungsstand meldet WP1 als erledigt, ohne die Lizenz zu nennen.
Der M0-Eintritts-Check führt das als P0-Rest R-09. Beide `README.md` schlossen den Statusabsatz mit
„Alle Rechte vorbehalten“; der Kontext von R-09 übersah das, weil die Suche nur englische Begriffe
enthielt. Es fehlten aber Rechteinhaber, Jahr, eine `LICENSE`-Datei und ein `license`- oder
`license-file`-Feld in den Manifesten beider Repos.

Am 2026-09-15 hat der PO entschieden, `grimoire` und `fiends-n-patrons` als neue öffentliche
GitHub-Repos mit bereinigter Historie zu veröffentlichen; die bisherigen privaten Repos bleiben als
Archiv. Der Grund: Das Kontingent an Actions-Minuten des privaten Tarifs ist fast aufgebraucht,
öffentliche Repos erhalten gehostete Standard-Runner kostenlos. Die Prämisse „privat“ aus WP1.4 fällt damit weg.

Zur Rechtslage, so wie die Quellen sie beschreiben (keine Rechtsberatung): Ohne Lizenz gilt das
Urheberrecht, niemand darf den Inhalt vervielfältigen, verbreiten oder bearbeiten
([GitHub Docs: Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository),
[choosealicense.com: No License](https://choosealicense.com/no-permission/)). Ein öffentliches Repo
erlaubt anderen GitHub-Nutzern nach den GitHub-Nutzungsbedingungen (Abschnitt D.5) nur, es auf GitHub
anzusehen und zu forken. Eine freie Lizenz lässt sich jederzeit nachträglich erteilen, für bereits
genommene Kopien aber nicht zurückholen.

Für das Spiel kommt hinzu: PRD-0001 hält einen späteren Verkauf (Steam, Mobile-Stores) ab Phase 2
offen. Eine permissive Lizenz würde jedem erlauben, das Spiel nachzubauen und weiterzuverbreiten.
E17 wünscht offen dokumentierte Datenformate für Modding, öffnet dafür aber nicht den Code.

## Anforderungen

- Der Lizenzstand beider Repos ist vor dem Umschalten auf öffentlich eindeutig und auffindbar festgehalten (R-09).
- Keine unwiderruflichen Rechte einräumen, solange der Vertrieb offen ist (PRD-0001, PRD-0017).
- GitHub und Cargo finden die Angabe maschinell: `LICENSE` im Wurzelverzeichnis, Feld im Manifest.
- Veröffentlichte Engine-Tags werden nicht verschoben (ADR-0009).
- Öffentliche Nightly- und Release-Binaries bleiben erlaubt (PO-Entscheidung vom 2026-09-15).

## Optionen

1. **Status quo: nur der Satz im README** — rechtlich ebenso restriktiv, aber ohne Rechteinhaber,
   Jahr und Datei. GitHub zeigt keine Lizenz an, R-09 bliebe offen.
2. **Alle Rechte vorbehalten, ausdrücklich, in beiden Repos (gewählt)** — `LICENSE` mit
   Copyright-Zeile und klarem Vorbehalt, `license-file` im Manifest. Räumt nichts ein und lässt jede
   spätere Lizenz offen.
3. **Engine permissiv (`MIT OR Apache-2.0`), Spiel vorbehalten** — folgt der Empfehlung C-PERMISSIVE
   der Rust API Guidelines für die Engine. Für genommene Kopien unwiderruflich; eine freie Weitergabe
   der Engine hat der PO nicht beschlossen.
4. **Source-available (etwa PolyForm Noncommercial oder BUSL) für eines oder beide Repos** — erlaubt
   eine eingeschränkte Nutzung. Bringt Bedingungen mit, die sorgfältig gewählt werden müssen, und löst
   kein aktuelles Problem.

## Entscheidung

Option 2 für beide Repos.

- **Rechteinhaber** ist Lupus Malus Deviant, Jahr 2026. Jedes Repo erhält eine `LICENSE` im
  Wurzelverzeichnis: englischer Vorbehaltstext ohne Erlaubnisse, Haftungsausschluss, Hinweis auf die
  eigenen Lizenzen der Fremdabhängigkeiten, deutsche Kurzfassung. Maßgeblich ist der englische Text.
  Die `LICENSE` des Spiels verweist zusätzlich darauf, dass Grimoire ein eigenes Repo mit eigenem
  Hinweis ist.
- **Manifeste:** `license-file = "LICENSE"` in `[workspace.package]`; jede Crate erbt das Feld mit
  `license-file.workspace = true`. Ein `license`-Feld entfällt, weil es für „Alle Rechte vorbehalten“
  keinen SPDX-Bezeichner gibt. `publish = false` bleibt. Geprüft mit Cargo 1.98.1: `cargo metadata`
  meldet für alle vier Spiel-Crates und alle dreizehn Engine-Crates `license_file` `../../LICENSE`
  ohne Warnung.
- **README:** In beiden Repos ersetzt ein Abschnitt „Lizenz“ den Satz im Statusabsatz.
- **Geltungsbereich:** der gesamte Repo-Inhalt, im Spiel also auch `content/`, `assets_src/`, Texte,
  Patterns und Doku, in allen Commits, Branches, Tags und Releases, auch in den Ständen vor der
  `LICENSE`-Datei. Engine-Tag `v0.1.0` wird dafür nicht neu gesetzt.
- **Formatdokumentation für Modding (E17)** erhält jetzt keine eigene Erlaubnis. Eine solche Freigabe
  ist ein eigenes, späteres ADR.
- Eine spätere Lizenzänderung ist ein neues ADR, das dieses ersetzt.

## Konsequenzen

- (+) R-09 ist geschlossen; WP1.4 aus Plan 0001 ist mit einem festgehaltenen Entscheid erfüllt.
- (+) Jede spätere Lizenz bleibt möglich, auch eine Öffnung der Engine oder der Formatdokumentation.
- (−) Außer dem Rechteinhaber darf niemand Engine oder Spiel nutzen, bearbeiten oder
  weiterverbreiten. Forks auf GitHub bleiben nach den Nutzungsbedingungen möglich, räumen aber keine
  Nutzungsrechte ein.
- (−) Ein externer Pull Request bringt ohne Vereinbarung keine Rechteeinräumung mit. Deshalb werden
  Pull Requests von außen derzeit nicht angenommen; Issues für Hinweise und Fehlerberichte bleiben
  offen (PO-Entscheidung vom 2026-09-15, [CONTRIBUTING.md](../../CONTRIBUTING.md), „Beiträge von
  außen“). Eine spätere Öffnung braucht eine Beitragsvereinbarung.
- (−) Öffentliche Binaries räumen ebenfalls keine Rechte ein; ob Spieler dafür eigene Nutzungsbedingungen
  brauchen, ist vor dem ersten veröffentlichten Release zu klären (offen). Die gelinkten Fremd-Crates
  (MIT, BSD, ISC, Apache-2.0, Unicode-3.0) verlangen, dass ihre Lizenzhinweise den Binaries beiliegen.
  `release.yml` erzeugt noch keine solche Datei; vor dem ersten veröffentlichten Spiel-Release ist
  eine Hinweisdatei für Drittanbieter-Lizenzen nötig.
- (−) Die Pläne und PRDs, die von privaten Repos oder privatem Vertrieb sprechen (Plan 0001, PRD-0017),
  beschreiben Sichtbarkeit und Vertrieb, nicht die Lizenz. Sie werden mit der Umstellung auf die
  öffentlichen Repos angepasst ([ADR-0013](0013-oeffentliche-repos-anonymer-engine-abruf.md)), nicht mit
  diesem ADR.
