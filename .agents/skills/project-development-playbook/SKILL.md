---
name: project-development-playbook
description: Use when implementing IdeaGo tasks that need branch, stack, and verification guidance.
---
# Project Development Playbook

This legacy skill is a thin Trellis pointer.

Read these files before editing:

1. `.trellis/spec/README.md`
2. `.trellis/spec/shared/index.md`
3. `.trellis/spec/backend/index.md` for backend work
4. `.trellis/spec/frontend/index.md` for frontend work
5. `.trellis/spec/shared/verification.md` before completion

Key branch rule: `saas` owns hosted auth, Supabase persistence, quota/admin,
LinuxDo recovery, and Stripe plumbing. Do not move those assumptions to `main`
unless the task explicitly targets both branches.
