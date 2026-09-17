# tests/fixtures/sigil-broken/

Absichtlich kaputte Sigil-Quellen für den **Negativnachweis** des Asset-Gates (Plan 0002 WP9.3).

Ein grünes Gate beweist für sich genommen nichts: Es wäre genauso grün, wenn der Compiler gar nicht
liefe, das falsche Verzeichnis läge oder sein Exit-Code verschluckt würde. Deshalb übersetzt ein
eigener CI-Job dieses Verzeichnis und ist **nur dann grün, wenn `grimoire-ac` mit einem Exit-Code
≠ 0 endet und jede in `expected-codes.txt` genannte Diagnose meldet**.

| Datei | Fehler | Erwartete Diagnose |
|---|---|---|
| `unknown_unit.sigil` | `5s` nennt eine Einheit, die die Sprache nicht kennt (Lexer) | `SIG0006` |
| `unknown_bullet.sigil` | Der Emitter feuert einen nie definierten Bullet-Typ (Schema-Durchgang) | `SIG0014` |

Zwei Dateien, damit beide Stufen des Compilers nachweislich ablehnen. Weitere Folgediagnosen sind
erlaubt (`unknown_unit.sigil` zieht `SIG0016` nach sich); die Liste in `expected-codes.txt` ist das
Minimum, nicht die vollständige Ausgabe.

**Diese Dateien gehören nie nach `content/`.** Dort übersetzt das Gate bei jedem Push, und jede
Diagnose bricht den Lauf — eine kaputte Datei in `content/` würde also die CI dauerhaft rot machen.
Aus demselben Grund liegen sie außerhalb von `content/`: Die Content-Discovery des Asset-Compilers
nimmt jede `.sigil`-Datei unterhalb ihrer Wurzel.
