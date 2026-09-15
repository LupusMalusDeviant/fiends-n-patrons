# ADR-0013: Öffentliche Repos und anonymer Engine-Abruf

- **Status:** Akzeptiert (2026-09-15; PO-Entscheidung zur Veröffentlichung beider Repos. Als umgesetzt gilt die Entscheidung erst mit dem ersten grünen CI-Lauf auf Windows, Linux und macOS im neuen öffentlichen Spiel-Repo, ohne Deploy-Key und ohne Secret)
- **Datum:** 2026-09-15
- **Entscheider:** Lupus Malus Deviant (PO), vorbereitet durch Claude
- **Ersetzt:** [ADR-0009](0009-engine-pin-ueber-git-tag.md), Entscheidung Teil 2 „CI-Zugriff über einen Read-only-Deploy-Key“ samt dem Umsetzungspunkt „Kein weicher Modus mehr“. Teil 1 (Pin über Tag) und Teil 3 (lokaler `[patch]`) gelten weiter.
- **Bezug:** [ADR-0002](0002-engine-eigenes-repo.md), [ADR-0009](0009-engine-pin-ueber-git-tag.md), [ADR-0012](0012-lizenz-alle-rechte-vorbehalten.md) (Lizenz), [PRD-0017](../prd/0017-plattform-ci-distribution.md) (FR-04, NFR), [Plan 0002](../plans/0002-phase-p1-sichtbarer-kern.md) (WP9.3, OP-6), [M0-Eintritts-Check](../plans/0002-m0-eintritts-check.md) (R-07, R-09)

## Kontext

ADR-0009 hat die Engine über eine Cargo-git-Dependency mit Tag angebunden. Weil beide Repos privat
waren, bekam die Spiel-CI einen eigenen Zugang: einen Read-only-Deploy-Key auf `grimoire`, dessen
privater Teil als Secret `GRIMOIRE_DEPLOY_KEY` im Spiel-Repo lag. Die lokale Action
`.github/actions/engine-access` lud ihn per `webfactory/ssh-agent` und lenkte die HTTPS-URL auf SSH um.
Eingerichtet und rotiert wurde er mit `scripts/setup-ci-deploy-key.ps1`.

Am 2026-09-15 hat der PO entschieden, beide Repos zu veröffentlichen. Anlass: Das Kontingent an
Actions-Minuten des privaten Tarifs ist fast aufgebraucht, und öffentliche Repos bekommen die
Standard-Runner (Linux, Windows, macOS) kostenlos. Umgesetzt wird das als **neue** öffentliche Repos
mit denselben Namen (`LupusMalusDeviant/grimoire`, `LupusMalusDeviant/fiends-n-patrons`) und
bereinigter Historie. Die alten privaten Repos heißen danach `grimoire-archiv` und
`fiends-n-patrons-archiv`. Beide Repos stehen unter „Alle Rechte vorbehalten“, Rechteinhaber
„Lupus Malus Deviant“ ([ADR-0012](0012-lizenz-alle-rechte-vorbehalten.md)). Öffentliche Nightly- und
Release-Binaries sind erlaubt.

Mit einer öffentlichen Engine verliert der Deploy-Key seinen Zweck. Das Veröffentlichungs-Audit
vom 2026-09-15 nennt dazu drei Befunde:

- **Überflüssiger Zugang.** Key und Secret wären danach ein Schlüssel ohne Aufgabe. Lebendig halten
  müsste man ihn trotzdem, denn er hängt am Token der GitHub CLI.
- **Grüne Läufe ohne Prüfung.** Pull Requests aus Forks und von Dependabot bekommen keine Secrets.
  `engine-access` überspringt für sie mit einer Warnung alle Cargo-Schritte, und der Job endet grün,
  obwohl nichts gebaut oder getestet wurde. In einem öffentlichen Repo sind solche Pull Requests der
  Normalfall.
- **Reihenfolge.** Wer den Key entfernt, bevor die Workflows umgestellt sind, macht jeden CI-,
  Nightly- und Release-Lauf rot. Die neuen Repos haben von Anfang an weder Secret noch Deploy-Key;
  die Umstellung muss also schon im ersten Push des neuen Spiel-Repos stecken.

**Kernfrage:** Wie holt die Spiel-CI die Engine, wenn beide Repos öffentlich sind, und was wird aus
dem Deploy-Key?

## Anforderungen

### Funktional

- Jeder Lauf von `ci.yml`, `nightly.yml` und `release.yml` baut und testet gegen den gepinnten
  Engine-Tag, **auch** bei Pull Requests aus Forks und von Dependabot. Einen grünen Lauf, der nichts
  geprüft hat, gibt es nicht.
- Der Pin aus ADR-0009 bleibt unverändert: Tag im Manifest, Commit im `Cargo.lock`, `--locked` in
  der CI.
- Ein frischer Klon baut ohne Einrichtungsschritt, lokal wie in der CI.

### Nicht-Funktional

- Keine Zugangsdaten in der CI, die nicht gebraucht werden (geringste Rechte, nichts zu rotieren).
- Möglichst wenig eigene CI-Vorrichtung und wenige Drittanbieter-Actions.
- Ein fehlgeschlagener Engine-Abruf ist im Log eindeutig als solcher erkennbar.
- Keine Kosten: nur Standard-Runner öffentlicher Repos.

## Betrachtete Optionen

### Option 0: Deploy-Key beibehalten

Die CI holt die Engine weiter über SSH mit dem Read-only-Key, obwohl sie öffentlich ist.

**Positiv:**
- Keine Workflow-Änderung. Die Spiel-CI bliebe grün, falls die Engine wieder privat würde.

**Negativ:**
- In den neuen Repos existieren weder Key noch Secret. Sie müssten neu angelegt werden, nur um
  etwas Öffentliches zu lesen.
- Fork- und Dependabot-Pull-Requests bleiben ungeprüft grün; das ist der eigentliche Mangel.
- Der Key hängt am Token der GitHub CLI und verschwindet, wenn diese Autorisierung widerrufen wird.
- Hält die Drittanbieter-Action `webfactory/ssh-agent`, die Composite-Action und das Setup-Skript am
  Leben.

### Option 1: Anonymer HTTPS-Abruf, Deploy-Key entfernt

Die Workflows rufen Cargo direkt auf. Cargo holt `https://github.com/LupusMalusDeviant/grimoire` ohne
Zugangsdaten. `.github/actions/engine-access`, `scripts/setup-ci-deploy-key.ps1`, das Secret und der
Deploy-Key entfallen.

**Positiv:**
- Jeder Lauf baut und testet, auch aus Forks. Die Unterscheidung `require`/Überspringen fällt weg.
- Kein Secret, kein Key, keine Rotation, keine Abhängigkeit vom Token der GitHub CLI.
- Rund 500 Zeilen eigene Vorrichtung (Composite-Action und Setup-Skript) und eine Drittanbieter-Action
  weniger.
- Das Manifest nennt die HTTPS-URL schon heute (ADR-0009: „neutral gegenüber dem Transport“), also
  ändern sich weder `Cargo.toml` noch `Cargo.lock`.
- Lokal entfällt `gh auth setup-git`.

**Negativ:**
- Die Spiel-Builds hängen an der öffentlichen Sichtbarkeit der Engine. Wird sie wieder privat, ist
  jeder Spiel-Build rot, bis ein neuer Zugang entschieden ist.
- Gelöschte oder verschobene Engine-Tags brechen nicht mehr nur die eigene CI, sondern jeden fremden
  Klon.

### Option 2: Zweiter `actions/checkout` der Engine plus Pfad-Patch

Die CI checkt die Engine am Tag neben dem Spiel aus und leitet Cargo per `[patch]` auf den Pfad um.

**Positiv:**
- Funktioniert anonym und nutzt den Checkout-Cache von GitHub.

**Negativ:**
- Ein aktiver `[patch]` bricht `--locked` (ADR-0009, Konsequenzen) und ersetzt die Quelle im
  Lockfile; der Pin würde in der CI nicht mehr geprüft.
- Den Tag gäbe es doppelt, in `Cargo.toml` und im Workflow. Das ist genau die Schwäche, die
  ADR-0009 an Option 3 verworfen hat.

### Option 3: Engine auf crates.io veröffentlichen

Die Engine-Crates werden bei jedem Tag auf crates.io veröffentlicht, das Spiel nutzt normale
Versionsangaben.

**Positiv:**
- Echte SemVer-Auflösung, kein Git-Abruf.

**Negativ:**
- Widerspricht `publish = false` und dem Release-Ablauf beider Repos; jeder Tag bräuchte einen
  Veröffentlichungsschritt mit Token in der Engine-CI.
- Veröffentlichte Versionen lassen sich nur zurückziehen, nicht löschen.
- Für genau einen Konsumenten überdimensioniert, wie schon die Registry in ADR-0009.

## Entscheidung

**Gewählte Option:** „Anonymer HTTPS-Abruf, Deploy-Key entfernt“ (Option 1)

Sie behebt den eigentlichen Mangel: Fork- und Dependabot-Pull-Requests wurden bisher nicht
geprüft. Außerdem entfernt sie einen Zugang, der nichts mehr schützt, und ändert am Pin aus ADR-0009
nichts. Option 0 hält Aufwand ohne Nutzen am Leben; die Optionen 2 und 3 opfern den geprüften Pin
oder bringen Veröffentlichungsaufwand.

Im Einzelnen:

1. **Workflows.** `ci.yml`, `nightly.yml` und `release.yml` verlieren den Schritt „Engine access“ und
   jede Bedingung `steps.engine.outputs.cargo == 'true'`. Jeder Cargo-Job führt vor dem ersten Build
   einen eigenen Schritt `cargo fetch --locked` aus, damit ein gescheiterter Engine-Abruf im Log
   nicht wie ein Compile-Fehler aussieht. `GIT_TERMINAL_PROMPT=0` und `GCM_INTERACTIVE=never` sorgen
   dafür, dass ein nicht erreichbares Repo sofort scheitert, statt auf eine Anmeldung zu warten.
2. **Entfernt** werden `.github/actions/engine-access/` und `scripts/setup-ci-deploy-key.ps1`. Im
   Archiv-Repo `fiends-n-patrons-archiv` wird das Secret `GRIMOIRE_DEPLOY_KEY` gelöscht, im Archiv-Repo
   `grimoire-archiv` der Deploy-Key „fiends-n-patrons CI (read-only)“. Die neuen Repos bekommen beides
   nie.
3. **Bleibt:** Teil 1 von ADR-0009 (Tag im Manifest, Commit im `Cargo.lock`, `--locked`, Tags werden
   nie verschoben oder gelöscht) und Teil 3 (lokaler `[patch]` außerhalb beider Repos). Die
   versionierte `.cargo/config.toml` behält `[net] git-fetch-with-cli = true`, damit lokal und in der
   CI derselbe Weg greift. Nötig ist die Einstellung nicht mehr.
4. **Kein Rückweg per Secret.** Soll die Engine je wieder privat werden, entscheidet ein neues ADR
   über den Zugang; die entfernte Vorrichtung wird nicht stillschweigend zurückgeholt.

## Konsequenzen

### Positiv

- Jeder CI-Lauf prüft tatsächlich, auch bei Pull Requests von außen und von Dependabot.
- Kein Zugang mehr zu verwalten: kein Secret, kein Deploy-Key, kein Setup-Skript, keine Rotation.
- Weniger Angriffsfläche in der Lieferkette: `webfactory/ssh-agent` entfällt.
- Ein frischer Klon baut ohne Vorbereitung; README und CONTRIBUTING werden kürzer.
- R-07 aus dem M0-Eintritts-Check („Engine-Checkout über den Deploy-Key in ADR-0009 dokumentieren“)
  entfällt. Der zweite Engine-Checkout für WP9.3 (Plan 0002, OP-6) braucht nur noch
  `actions/checkout` mit `repository` und `ref`, ohne `ssh-key`.

### Negativ

- Die Spiel-Builds hängen an der öffentlichen Sichtbarkeit der Engine. Wird `grimoire` privat oder
  umbenannt, sind alle Spiel-Läufe rot.
- Die Tag-Regel aus ADR-0009 wiegt schwerer: Ein verschobener oder gelöschter Engine-Tag bricht jetzt
  auch fremde Klone und alte Spiel-Stände.
- Während der Umbenennung der alten Repos lenkt GitHub den alten Namen auf das Archiv um. Bis das
  neue Repo unter dem Namen existiert, zeigt die URL im `Cargo.lock` auf ein privates Repo. Mit
  eigenen Zugangsdaten (Credential-Helper der GitHub CLI) klappt der Abruf dann trotzdem und
  täuscht Erfolg vor. Nachgewiesen wird deshalb nur anonym (siehe „Weitere Informationen“).
- Das neue Spiel-Repo startet ohne Actions-Cache; die ersten Läufe dauern länger.
- Öffentliche Repos lassen Pull Requests von Fremden zu, die Runner-Zeit binden. Dagegen hilft die
  Einstellung, Workflows externer Beitragender erst nach Freigabe laufen zu lassen (PO-Entscheidung
  vom 2026-09-15).
- Plan 0002 (WP9.3, OP-6), PRD-0017 (OF-17.1), der M0-Eintritts-Check und das Sammelsitzungs-Dossier
  nennen den Deploy-Key noch. Sie werden mit dieser Umstellung nachgezogen: lebende Dokumente im
  Wortlaut, Protokolle mit datierten Nachträgen.

## Weitere Informationen

**Reihenfolge der Umstellung** (aus dem Audit, angepasst an neue Repos):

1. Historie beider Repos umschreiben; Engine-Tag neu setzen; `Cargo.lock` des Spiels auf den neuen
   Tag-Commit ziehen.
2. Alte Repos umbenennen (`grimoire-archiv`, `fiends-n-patrons-archiv`), dann das neue öffentliche
   `grimoire` anlegen und Historie samt Tags pushen.
3. Anonym prüfen: `git ls-remote` des Tags ohne Credential-Helper nennt den Commit aus `Cargo.lock`,
   und `cargo fetch --locked` gelingt mit leerem `CARGO_HOME`.
4. Neues öffentliches `fiends-n-patrons` anlegen und die Historie pushen, einschließlich des Commits
   mit dieser Umstellung.
5. Den ersten CI-Lauf mit `gh run watch --exit-status` bis zum Ende überwachen. Im Log steht in jedem
   der drei `test`-Jobs unter „Fetch dependencies“ die Zeile
   ``Updating git repository `https://github.com/LupusMalusDeviant/grimoire` ``.
6. Erst danach Secret und Deploy-Key in den Archiv-Repos löschen.

Statuswechsel von ADR-0009: nur die Statuszeile und ein Verweis auf dieses ADR; der Inhalt bleibt als
Zeitkapsel stehen.
