# Third-Party Notices

## Scope of the project license

The MIT license in `LICENSE` applies only to the MathModel Weave material that
this repository's contributors authored and that is identified as project-owned.
It does not relicense third-party software, host dependencies, embedded fonts,
research materials, competition rules, user data, or generated material whose
rights belong to someone else.

The product implementation, product skills, templates, examples, and project
documentation were reviewed on a limited, targeted basis. The publication
template notice files record that the `ctexart`-based template, `cumcm.mplstyle`,
redraw code, and demonstration paper text were independently written for this
project. That review found no copied SciencePlots parameters or copied
K-Dense, academic-writing-skills, or figures4papers text, scripts, styles,
parameters, or images in the checked product material.

## Dependencies and host prerequisites

The Python package declares `matplotlib`, `openpyxl`, and `pypdf` as external
runtime dependencies. Their code is not relicensed by this repository; users
must retain and follow the license and notice terms supplied by each package
when redistributing those packages or a distribution that includes them.
`hatchling` is an external build dependency with the same separation.

XeLaTeX, CTeX, xeCJK, `zhnumber`, Poppler, fontconfig, and Noto CJK fonts are
normally host prerequisites for the publication workflow, not source packages
in the portable product source scope. The local development environment also
contains `.runtime/d5-texmf-home/` with TeX package files and `tlpkg/tlpobj`
metadata. CTeX, xeCJK, and zhnumber are marked `LPPL 1.3c` in that environment's
package metadata; those files are not covered by the project MIT license.

The source distribution scope excludes local environments and caches including
`.venv/`, `.runtime/`, `.test-tmp/`, `.pytest_cache/`, and `__pycache__/`.
If a user distributes any of those directories anyway, the licenses for the
packages and files actually included must travel with them and be checked
separately.

The Noto CJK fonts used by the reviewed PDFs are `NotoSerifCJKjp` and
`NotoSansCJKsc`. The installed package metadata identifies the font copyright as
`2010-2012, Google Corporation` and the license as SIL Open Font License 1.1.
The exact license text is preserved in `licenses/OFL-1.1.txt`; its source
package record is `/usr/share/doc/fonts-noto-cjk/copyright` and upstream source
is `https://github.com/notofonts/noto-cjk`. OFL 1.1 permits embedding and
redistribution with software when its copyright notice and license are retained;
documents created using the fonts are not required to be licensed as font
software under OFL.

The reviewed demonstration PDFs under
`examples/publication/synthetic-paper/build/paper/` contain embedded font data
according to their existing build report and the targeted `pdffonts` check.
The Noto CJK attribution and OFL text above should accompany redistribution of
those PDFs. The repository does not ship the corresponding standalone font
files, and `LICENSE` does not relicense the embedded font data.

## Research references and non-incorporated material

The repositories under `skills_baselines/`, `multi_agent_baselines/`, and the
publication candidate directory are research and comparison material. Their
licenses are not inherited by this product, and their code, text, styles,
images, and restricted or non-commercial assets were not treated as product
inputs merely because they were studied.

In particular, the MathMN baseline carries PolyForm Noncommercial terms; the
figures4papers material is marked CC BY-NC 4.0; and academic-writing-skills
material was marked Academic Use Only without a separately verified repository
license. These restrictions are why the reviewed product does not copy those
materials. The applicable baseline license files remain at their original
paths and are not replaced by this notice.

SciencePlots, TUEplots, and the CUMCM template candidate have MIT license texts
in the local research candidate directory. They informed comparison only; no
SciencePlots code or parameters were found in the product review, and no
candidate license is a substitute for the product `LICENSE`.

The product's publication notices are retained at:

- `templates/publication/THIRD_PARTY_NOTICES.md`
- `examples/publication/synthetic-paper/build/paper/THIRD_PARTY_NOTICES.md`

Those notices describe the publication-specific boundary and must travel with
the corresponding template or generated paper package where applicable.

## User-facing summary

For project-owned material covered by `LICENSE`, users may use, copy, modify,
publish, distribute, sublicense, and sell copies, subject to keeping the MIT
copyright and permission notice and accepting the warranty disclaimer. Users
must separately preserve the licenses, copyright notices, attribution, and any
other conditions for third-party packages, fonts, TeX components, PDFs, data,
or other material that they actually redistribute. Academic citation is not a
substitute for permission.

This file is a bounded provenance and license inventory, not a comprehensive
infringement, ownership, font, data, or competition-rules determination.
