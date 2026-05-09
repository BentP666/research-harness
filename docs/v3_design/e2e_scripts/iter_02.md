# Iter-02 E2E Script — Onboarding Persona Branching

## Pre-requisites
- Backend running at localhost:8000
- Frontend running at localhost:3000

## Steps

1. Navigate to `http://localhost:3000/onboarding`
2. **Screenshot**: initial persona step (4 cards visible)
3. Click "New to AI Research" (p1) → step count should show 5 dots
4. **Screenshot**: p1 selected with 5 steps
5. Click "Back", then click "Topic + Seeds" (p4) → step count should show 6 dots
6. **Screenshot**: p4 selected with 6 steps
7. Click "Next" → Topic Brief placeholder page
8. Click "Next" → Seed Material placeholder page
9. Click "Next" → Constraints step
10. Select "Locked" venue → venue text input appears
11. Type "EMNLP" in venue input
12. Select "Single GPU" compute budget
13. Select 120 days deadline
14. **Screenshot**: constraints step filled
15. Click "Next" → Agents step
16. **Screenshot**: agents step (needs 2 agents)

## Mobile verification (375×667)
17. Resize to 375×667
18. Navigate to `/onboarding`
19. **Screenshot**: persona cards single column, no overflow
20. Select p3 → Constraints
21. **Screenshot**: compute options wrap correctly

## Assertions
- [ ] 4 persona cards render correctly
- [ ] p1 → 5 steps, p4 → 6 steps
- [ ] Constraints step shows venue input only when Locked/Preferred
- [ ] Mobile layout doesn't break
- [ ] CN/EN switch works (toggle locale, verify persona card text changes)
