# PRD: C4 + ADR demó repó (lead magnethez)

## Goal

Egy angol nyelvű, nyilvános GitHub demó repó, amin végigkattintható egy történet arról, hogyan működik együtt a C4 modell és az ADR (Architecture Decision Record) folyamat egy repóban. A repó egy lead magnet dokumentumot kísér, ami ugyanezt a flow-t mutatja be.

## Problem

A C4-et és az ADR-eket sokan ismerik külön-külön, de ritkán látni, hogyan kapcsolódnak össze a mindennapi munkában. A demónak három üzenetet kell egyetlen végigkövethető történetként megmutatnia:

1. Az ADR-ek és a C4 diagramok együtt változnak, egy PR-ban.
2. Döntés → diagram frissítés: az ADR indokolja a C4 változást.
3. Docs-as-code: az architektúra a kód mellett él, review-zva, verziózva, CI-jal kikényszerítve.

## Users and journeys

- **Közönség:** vegyes – kezdőknek is érthető legyen (aki még nem használt C4-et/ADR-t), de senior / tech lead / architekt számára is adjon hasznosat (hogyan kössék össze a kettőt, CI-jal kikényszerítve).
- **Fő út:**
  1. Az olvasó a lead magnet doksiból érkezik (a doksi közvetlenül a PR-okra linkel, a képei a CI által renderelt diagramok).
  2. A README „Walkthrough” fejezete a doksi lépéseit tükrözi, és sorrendben végigvezet a PR-okon.
  3. Minden merged PR-ban látja: az új ADR-t, a DSL diffet, a bot kommentet a régi/új diagrammal, és a szerepkörös review kommenteket.
  4. A nyitott PR-ban (ADR-0007) látja, hogy a CI elbukott, amikor csak a DSL változott, majd zöld lett, amikor az ADR is bekerült.
  5. A GitHub Pages-en publikált Structurizr oldalon böngészi a teljes modellt és a beemelt ADR-eket.

## In scope

### Tartalom
- **Domain:** képzeletbeli webshop / e-commerce rendszer.
- **Csak dokumentáció:** C4 modell, ADR-ek, CI – nincs futtatható alkalmazáskód.
- **C4:** Structurizr DSL workspace, nézetek: System Context, Container, Component (egy containerre), valamint Deployment és Dynamic nézet.
- **ADR:** MADR sablon szerinti markdown fájlok, a Structurizr workspace-be `!adrs` direktívával beemelve.
- **Döntéslista (történetív):**
  1. ADR-0001 – Record architecture decisions
  2. ADR-0002 – Start with a modular monolith
  3. ADR-0003 – Use PostgreSQL
  4. ADR-0004 – Payments via an external PSP (Stripe)
  5. ADR-0005 – Synchronous REST between Order and Inventory
  6. ADR-0006 – Introduce an event bus (RabbitMQ) — **supersedes ADR-0005**
  7. ADR-0007 – Extract Order into a separate service — **Proposed**, nyitott PR-ban
- Minden ADR-hez tartozik a megfelelő C4 változás ugyanabban a PR-ban.

### GitHub flow
- ADR-0002…0006: lezárt (merged) PR-ok, mindegyikben egy döntés + a hozzá tartozó DSL változás, review kommentekkel. (ADR-0001 lehet a kezdő commit része.)
- ADR-0007: nyitott PR. Első commit csak a DSL-t módosítja → CI piros; második commit hozzáadja az ADR-t → CI zöld. A piros futás a PR history-ban látható marad.
- Review kommentek egy GitHub fiókból, a szövegben megnevezett szerepkörökkel (pl. „As the security lead…”).

### CI (GitHub Actions)
- Structurizr DSL validálás.
- DSL↔ADR ellenőrzés: ha a **modell** (elemek, kapcsolatok) változik, a PR-nak új vagy módosított ADR-t is tartalmaznia kell (és fordítva). A csak `views` / `styles` változás nem triggereli.
- Diagramok renderelése (PNG/SVG): workflow artifactként, és bot komment a PR-ban a régi és új diagrammal.
- Publikálás GitHub Pages-re (Structurizr static site, a beemelt ADR-ekkel). A README és a lead magnet doksi képei innen / az artifactokból származnak; renderelt képek nincsenek a repóba commitolva.

### Nyelv
- A repó teljes tartalma (README, ADR-ek, DSL, PR leírások, kommentek) angol.

## Out of scope

- Futtatható kód, vázkód vagy mini alkalmazás.
- Maga a lead magnet dokumentum megírása (a repó csak kíséri).
- Issue-alapú flow (a döntések nem issue-kból indulnak).
- Több valódi GitHub fiók a review-khoz.
- Renderelt diagramképek commitolása a repóba.
- Újrahasználható template repó: ez külön repó és külön munka lesz; ez a repó csak demó, nem GitHub template repository.

## Success criteria

- Az olvasó kb. 10–15 perc alatt végig tudja kattintani a README walkthrough-t.
- Minden merged PR-ban zöld a CI, és a bot kommentben látszanak a renderelt (régi/új) diagramok.
- A nyitott PR-on látszik, hogy a CI elbukik ADR nélkül, majd zöld lesz az ADR hozzáadása után.
- A GitHub Pages oldal elérhető, és mutatja az összes nézetet és ADR-t.
- A CI workflow-k és a repó struktúrája elég tiszta ahhoz, hogy a későbbi külön template repó alapja legyen.

## Constraints

- Nyilvános GitHub repó: `letscodehu/c4-adr`, MIT licenc (már a repóban).
- Minden tartalom angolul.
- Nincs fix határidő.

## Open questions and assumptions

- **Feltételezés:** a renderelés és Pages publikálás ingyenes, nyílt eszközökkel megy (pl. Structurizr CLI / structurizr-site-generatr), Structurizr Cloud nélkül.
- **Feltételezés:** a review szerepkörök a domainhez illők (pl. tech lead, security lead, SRE/ops), a konkrét szövegeket a megvalósításkor írjuk meg.
- **Feltételezés:** a PR-ok sorrendje megegyezik az ADR-ek számozásával, és a README walkthrough ugyanezt a sorrendet követi.
