# Dvora Attorneys visual identity

The photographed business card establishes the deep navy identity, firm name,
tagline, and contact information. The website develops that identity into a
formal navy, warm ivory, and muted gold palette. These are coordinated digital
colors, not exact print-color measurements from the photograph.

## Color formula

Use approximately **60% warm neutral surfaces, 30% navy, and 10% gold accents**
across the experience. Large navy hero/sidebar panels can reverse the balance.
Use gold for emphasis, rules, icons, and selected actions; dark navy provides
readable text on gold buttons. State colors communicate status rather than brand.

| Purpose | CSS variable | Hex |
| --- | --- | --- |
| Primary brand/navy | `--navy` | `#191B43` |
| Hero/sidebar/deep navy | `--navy-deep` | `#11132F` |
| Navy hover surface | `--navy-soft` | `#26294F` |
| Gold accent | `--gold` | `#BBA16B` |
| Gold text on pale surfaces | `--gold-deep` | `#80652F` |
| Main background/ivory | `--ivory` | `#F7F5EF` |
| Panels/paper | `--paper` | `#FFFEFA` |
| Body text | `--ink` | `#25283A` |
| Secondary text | `--muted` | `#686B79` |
| Borders | `--line` | `#E3E1D9` |
| Success text | `--success` | `#28634D` |
| Success background | `--success-bg` | `#EDF5EE` |
| Destructive/error text | `--danger` | `#A23737` |
| Error background | `--danger-bg` | `#FBEFED` |

The source of truth is `core/static/core/css/site.css`, in the `:root` block.
Change shared tokens there instead of assigning different brand colors per page.
Use deep gold rather than the lighter decorative gold for small text on ivory.
Status badges also include text, so their meaning does not depend on color alone.

## Typography and layout

- Georgia/Times serif for editorial headings; Segoe UI/Arial sans serif for body,
  controls, forms, and data. Fonts are local/system fallbacks, with no external
  font requests or build step.
- Keep generous margins on the public site, short supporting paragraphs, and
  restrained rules. The homepage uses a centred, text-led hero.
- Management pages use the same sidebar, account bar, table styles, form styles,
  focus indicators, error treatment, and pagination.
- At narrow widths, the sidebar becomes top navigation and data tables scroll
  within their panels. Buttons and inputs retain usable touch dimensions.
- Respect reduced-motion preferences. Public and sign-in pages include skip links.

## Logo

`core/static/core/images/dvora-logo.svg` is a clean vector interpretation inspired
by the logo on the supplied business card, using a scales/person motif and the
Dvora wordmark. It is a recreation, not an exact traced original. Replace this
file with the original exported brand asset if exact logo fidelity is needed.
The sidebar and sign-in panel show a white version through CSS filtering.

The monogram on the firm introduction is a decorative DA signature. It does
not replace the main brand mark.

## Content from the supplied card

- Dvora Attorneys at Law
- “Your trusted attorneys at service.”
- Magreth Asifiwe Mbasha — Managing Partner
- +255 672 946 109; +255 752 612 871
- dvoraatlaw@gmail.com
- Uhindini Street, Dodoma, Tanzania (map search: near LeRai Dry Cleaners; landmark omitted from the displayed address)
- P.O. Box 1404, Dodoma

The map link searches the supplied area; it does not claim verified coordinates.
No founding year, awards, client counts, testimonials, or specific practice
specialisms have been invented. Telephone and email links use the supplied details.

## Main files

- `core/templates/core/home.html`: public homepage, office details, and contact links.
- `clients/templates/clients/base.html`: shared management layout.
- `core/templates/registration/login.html`: dedicated sign-in design.
- `core/static/core/css/site.css`: shared palette and responsive rules.
- `core/static/core/images/`: vector brand and UI icons.

## Verification

All 50 existing application/API tests passed after the design changes. Django
checks and static-file discovery passed. Headless Chrome screenshots were
inspected for desktop/mobile homepages, the case workspace, and the sign-in
page. Workspace preview records were temporary, with no changes to development
client/case records. The design was implemented in the existing local Django
project and has not been published to hosting.
