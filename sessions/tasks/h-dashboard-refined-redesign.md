# Task: Dashboard Refined Minimalist Redesign

**Status:** Active
**Priority:** High
**Created:** 2025-11-18
**Aesthetic Direction:** Refined Minimalist

## Objective

Redesign DefectDojo's dashboard with a refined minimalist aesthetic that prioritizes surgical precision, unexpected typography, and whisper-quiet elegance. This is a security/vulnerability management platform that should feel professional, calm, and authoritative.

## Aesthetic Vision: "Refined Minimalist"

**Core Principles:**
- Ultra-clean layouts with dramatic whitespace
- Surgical precision in alignment and spacing
- Unexpected serif fonts for display text
- Whisper-quiet color palette (muted tones, subtle gradients)
- Restrained but meaningful micro-interactions
- Every detail intentional, nothing accidental

**Visual Language:**
- **Typography:** Distinctive serif for headings (Cormorant Garamond, EB Garamond), refined sans-serif for body (Manrope, Work Sans)
- **Color:** Warm gray base (#F5F5F3), muted sage accent (#8B9B8E), soft shadows
- **Spacing:** Generous negative space, asymmetric layouts, breathing room
- **Effects:** Soft shadows, subtle transitions, gentle hover states
- **Motion:** Restrained animations - staggered fade-ins on load, smooth hover transitions (200-300ms)

## Current Issues to Fix

1. **Critical Bug:** Dashboard template not rendering - `<body>` tag missing from browser output
2. **Generic Design:** Current attempt uses Inter font, basic Tailwind, zero creative direction
3. **No Differentiation:** Looks like every other Tailwind dashboard

## Todo List

- [ ] Fix critical rendering bug - body tag missing
- [ ] Design refined minimalist color palette and typography
- [ ] Create distinctive serif + sans-serif font pairing
- [ ] Build refined stat cards with subtle shadows
- [ ] Style Chart.js with minimalist aesthetic
- [ ] Implement subtle page-load animations
- [ ] Test and refine dark mode variant

## Success Criteria

- [ ] Template renders completely (all HTML tags present)
- [ ] Design feels distinctive and memorable
- [ ] Typography choices are unexpected but appropriate
- [ ] Color palette is cohesive and whisper-quiet
- [ ] Spacing creates breathing room and elegance
- [ ] Animations are subtle and refined
- [ ] User feedback: "This looks professional and different"
- [ ] No resemblance to generic Tailwind dashboards

## Technical Constraints

- Django templates (server-rendered)
- Must integrate with existing DefectDojo backend
- Chart.js for data visualization
- Maintain accessibility standards
- Support dark mode
- Mobile-first responsive design

## Anti-Patterns to Avoid

- ❌ Inter, Roboto, Arial, system fonts
- ❌ Purple gradients on white backgrounds
- ❌ Cookie-cutter card layouts
- ❌ Predictable component patterns
- ❌ Generic "modern" dashboard aesthetics
- ❌ Excessive animations or flashy effects
- ❌ Equal distribution of colors (needs dominance + accents)

## Reference Links

- Frontend Design Skill: /SKILL.md
- Current broken template: dojo/templates/dojo/dashboard_modern.html
- Base template: dojo/templates/base_modern.html
- Design system doc: DESIGN_SYSTEM.md

## Notes

This is a security platform. The design should feel:
- **Authoritative** but not intimidating
- **Precise** like surgical instruments
- **Calm** like a quiet library
- **Professional** like a high-end consultancy
- **Trustworthy** through clarity and refinement

Think: Scandinavian design meets financial services. Muted, sophisticated, quietly confident.
