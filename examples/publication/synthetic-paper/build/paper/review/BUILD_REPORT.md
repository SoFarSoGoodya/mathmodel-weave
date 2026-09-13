# Publication Build Report

Status: `review_ready`

- Publication ID: `PUB-synthetic-allocation-demo-v1`
- Demonstration: `true`
- Manifest SHA-256: `e83f807ab904003c66faa97c5e7c2894e6b4d86c5aca08773e261d15616970b6`
- Electronic PDF: `paper-electronic.pdf`
- PDF SHA-256: `7754c52d3066d5204807b599a67e825082360d890c41dcb7b975c5425c1ef10f`
- Pages / bytes: `8` / `263239`
- Embedded fonts checked: `21`
- Text layer characters: `10259`
- Rendered pages: `8`
- Body end page: `7`
- AI details pages / fonts: `1` / `5`
- Citation keys used: `D4SyntheticRun`
- Print target: `not configured`

## Checks

- selected result and evidence freeze match the exact run manifest SHA-256
- official/regional rule source is present and the rule config hash is selected
- result macros and table rows were generated deterministically from the manifest
- figure rows match complete saved observations; no undefined interval was drawn
- citation keys, placeholders, first-page rules, anonymity terms, critical numbers, PDF size, fonts, and text layer passed
- every electronic PDF page was rasterized for visual inspection

## Visual Review

Inspected all pages: `1, 2, 3, 4, 5, 6, 7, 8`.
- 最终零 overfull 版本逐页检查 1--8 页：无重叠、裁切、缺字或异常分页。
- 摘要独占第一页；公式、生成 Metric 表、两类正式图、跨页追溯表、AI 声明、参考文献和附录均清晰可读。
- 颜色之外使用 marker、线型、hatch 和状态文字；未绘制运行包没有定义的误差区间。
- AI 工具使用详情最终页已检查：七列表格位于版心内，开发夹具披露清晰，无 overfull。

## Limitations

- review_ready still requires actual inspection of every rendered page; compilation alone is insufficient
- the included specialized redraw handles the allocation demonstration; new scientific figure schemas require a task-specific renderer or an honestly disclosed original-image adoption
- the rule config is a frozen project interpretation and must be updated from current official and regional sources for each competition
- demonstration AI adoption facts are interface fixtures and do not represent live human approval
