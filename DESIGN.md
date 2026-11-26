# Design

Written before generating anything; the two user tests and what they changed are appended below.

## The story

*Enatenesh (እናቴነሽ).* My father raised me on his own. He carried me on his shoulders
everywhere and held my hand on the way to school. Once, while carrying me, we both fell and he
lost consciousness; I cried until he woke up. He brought me snacks, combed my hair, took me to
restaurants, helped me study, and called me "Chegura!" (ጨጓራ) when I couldn't answer. We talked
like friends. At coffee with the neighbours he would proudly say "I am Geremew's son!" He was a
teacher his students loved. Of all the names he called me, the one I remember is *Enatenesh*.

**Logline:** A daughter remembers the father who raised her alone, and the special name he called
her: Enatenesh.

**Story revision before any generation (10:06):** the first draft ended on the nickname *Alemé*
("my world"). I changed it to *Enatenesh*, the name he actually used most for me, added the hand
on the way to school, the coffee gathering, and the phone detail. Shot count and structure kept.

## Audience, place, feeling

- **Who:** my sisters Helen and Hana, my best friend Beza, then our wider family and friends.
  All Amharic speakers who know or knew him.
- **Where:** on their phones, vertical, shared over Telegram and WhatsApp. A public post follows.
- **Feeling at the end:** warm gratitude, a smile through tears. They should recognise him in
  the small, ordinary moments rather than in big events.

## Decisions before generating

- **Narrated in Amharic by a generic Gemini TTS voice**, not a cloned voice. The narrator is
  the grown daughter (me).
- **Hand-painted gouache illustration, not photoreal.** It reads as memory, it is kinder to a
  real person's likeness, and stylised faces hold identity across shots better.
- **Few characters** (father; daughter as a child; daughter grown up, s11 only), one outfit each except his suit in s11, to limit drift. Neighbours and students appear only as background.
- **One motif:** her on his shoulders. It opens (s01) and closes (s11) the film.
- **Cut to the voice:** each shot lasts as long as its narration line plus padding, so the
  radio cut fixes the timing before any picture exists.
- **s08 (Chegura, talking like friends) and s11 (Enatenesh) keep their full narration.** They are
  the heart of the story. If the film runs over 90 s, cut pauses and other lines first.
- **"Enatenesh" is not translated in the subtitles (12:21).** I first glossed it as "you are my
  mother". That is the literal reading, but it is an affectionate way of expressing love, not a
  statement, and the literal gloss misleads. Title changed to "Enatenesh — A Father's Love";
  the film is credited "A story by Segenet".
- **New ending (13:48).** After seeing the first keyframes I changed s11 from walking into the
  sunset on his shoulders to me as a graduate, in gown and cap, walking arm in arm with him in a
  suit. The opening (on his shoulders) and the ending (beside him, grown up) now show the whole
  arc of what he gave me. Added a third character reference, the grown daughter, and per-shot
  outfit overrides so he can wear a suit in that shot only.
- **Every shot has a stated reason** in `storyboard.json` (`reason` field).

## User test 1: radio cut (v3, 88 s, sent 12:45, answers by 14:10)

Testers: Helen (sister), Hana (sister), Beza (best friend); all native Amharic speakers.
Questions: what is it about; what did you feel; anything confusing, too fast or too slow;
any word pronounced wrongly; does the voice sound like one person; what would you remove or add.

| | Helen | Hana | Beza |
|---|---|---|---|
| What it's about | "A girl who loves her father, but she lost him" | "About a father and his love for his child" | "About a father" |
| Feeling | "I cried" | "I cried. He was much more than this, but in 90 seconds you express most of it, especially your nickname" | (not answered) |
| Pace | Did not notice a problem | (not answered) | "Too much break between the paragraphs" |
| Pronunciation | ጨጓራ mispronounced, and the subtitle gives it no meaning | መምህር mispronounced | ያስተዋውቀኝ mispronounced |
| One voice? | "No, after 0:56 it sounds like a different voice" | "Around 0:54 it changed the voice" | "Yes, the same person" |
| Remove / add | | Remove ተዋጊ, just say ጀግና | Add the graduation picture with your father at the end |

**What lands:** the story and the nickname. Two of three cried. Nobody asked to cut anything.

**What changed because of it:**
1. **One TTS model for every line.** The voice change at 0:54 is exactly where the quota
   fallback switched models (s09, FAILURES F4). Fallbacks are now disabled for narration and
   every line is regenerated on one model; the stage stops rather than mixing voices.
2. **Pronunciation.** ያስተዋውቀኝ → ያሳየኝ (s07) and መምህር → አስተማሪ (s09); ጨጓራ is respelled ጨግዋራ
   for the TTS (EXPERIMENTS E5).
3. **ጨጓራ explained honestly.** Helen said the subtitle gave the word no meaning. I realised the
   script itself was misleading: ጨጓራ has no literal meaning and was not about wrong answers; it
   was just his saying. The line now says he called me "Chegwara!" playfully, and the subtitle
   calls it "a saying all his own".
4. **s10:** "ጀግና ተዋጊ" should become "ጀግና" (Hana). Written into the script, but the TTS
   quota ran out before it could be voiced (FAILURES F9); the film keeps the earlier recording
   and its subtitle says "a brave warrior" to match. Same for መምህር in s09.
5. **Shorter pauses** between lines (Beza): 0.15 s before and 0.3 s after each line, minimum shot 3 s.
6. **Graduation ending** (Beza) had already been added at 13:48, so this confirmed it.

## User test 2: near-final cut (film v3, 84 s, sent 18:35, answers by 19:29)

Same testers. Beza's answers had not arrived at the time of writing.

| | Helen | Hana |
|---|---|---|
| Overall | "The film looks good... I'm proud of you. The way you tried to express him in these seconds is brave of you" | "You are making me cry" |
| Pictures | "The image looks good"; "the little girl looks like you" | "The girl looks much like you"; childhood setting right ("we were in a suburban place when we were kids") |
| Script and voice | "The way they express the script is good" | "Some words' pronunciation is still not correct"; "the warrior part is not changed as I gave in my comments before" |
| What did not work | "The coffee ceremony is not expressed well"; "if it was a video with movements it would be better, but it still expresses the scenes" | "Some images did not match the script, sometimes late"; graduation should be in a modern city ("after we grew up we moved to a better city") |
| Wish | | "Next time make a full short film with more memories" |

**What lands:** the likeness of the girl (both, unprompted), the story, the narration. Both were
moved again.

**What I changed or found because of it:**
1. **"Late" pictures, measured.** Every cut lands within 0.02 s of its planned time, so it is not
   sync. The real cause is content: several lines carry two ideas over one picture (s02 opens with
   "carried me on his shoulders" over the hand-holding picture; s08, s10, s11 each hold one image
   for 10 to 17 s). The fix is more shots, one picture per idea: next version.
2. **The warrior line (Hana, second time).** s10's narration is now "ጀግና" and only that line
   was regenerated (one TTS line; every other output came from the cache, see `runs.jsonl`).
3. **Graduation in a modern city (Hana).** She asked for exactly what I had wanted at 16:13 and
   could not generate after Cloudflare's daily allowance ran out (FAILURES F10). Next version.
4. **Coffee ceremony (Helen).** Confirms what I saw: the weakest image even on the 9B model
   (EXPERIMENTS E7, E8).
5. **Motion (Helen).** She would have liked movement; the Wan clips I made were worse than the
   pans because faces drifted (E11). Kept the pans, and noted that a better video model on a
   bigger GPU is worth it for this audience.
