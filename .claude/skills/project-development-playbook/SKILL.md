---
name: project-development-playbook
description: Use when implementing IdeaGo tasks that need branch, stack, and verification guidance.
---
# Project Development Playbook


Read these files before editing:


Key branch rule: `saas` owns hosted auth, Supabase persistence, quota/admin,
LinuxDo recovery, and Stripe plumbing. Do not move those assumptions to `main`
unless the task explicitly targets both branches.
