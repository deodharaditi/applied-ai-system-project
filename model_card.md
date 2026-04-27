# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**VibeMatcher 1.0**

---

## 2. Goal / Task

VibeMatcher suggests songs from a small catalog based on a user's stated taste preferences. It tries to find songs that feel closest to what the user wants — not just by genre label, but by matching the actual sound qualities like energy level, tempo, and emotional tone. It is built for classroom exploration, not for real-world deployment.

---

## 3. Algorithm Summary

Every song gets a score based on how well it matches the user's preferences. The scoring works in two steps.

First, genre and mood are checked as yes/no questions. If the song's genre matches the user's favorite genre, it gets 2 points. If the mood matches, it gets 1.5 points. No partial credit — either it matches or it doesn't.

Second, the remaining features — energy, emotional tone (valence), tempo, acousticness, vocal density (speechiness), and instrumentalness — are scored by closeness. A song that has almost the same energy as the user's target gets nearly full points. A song that is far off gets fewer points. The idea is that a song is not better just because it has a high energy value; it is better because its energy is *close to what this specific user wants*.

All scores are added up. The maximum possible score is 9.50 points. Songs are then ranked from highest to lowest, and the top 5 are returned as recommendations.

---

## 4. Data

The catalog has 20 songs stored in a CSV file. Each song has 17 attributes: id, title, artist, genre, mood, energy, tempo_bpm, valence, danceability, acousticness, speechiness, instrumentalness, popularity, release_decade, liveness, loudness_norm, and explicit.

The catalog covers 14 genres including lofi, pop, rock, jazz, folk, blues, metal, hip-hop, r&b, classical, edm, synthwave, country, and k-pop. Moods include chill, focused, happy, intense, melancholic, sad, aggressive, peaceful, and more.

Most genres have only one song. Lofi has three songs and pop has two — every other genre has exactly one. The catalog was generated to cover technical feature diversity, not cultural diversity. Real artist names, lyrics, and cultural context are absent. The data skews toward higher energy songs and heavily toward low speechiness, meaning rap and spoken-word listeners are underrepresented.

---

## 5. Strengths

The system works best when the user's preferred genre has more than one song in the catalog. The Late-Night Studier profile (lofi / focused) produced a near-perfect result — Focus Flow scored 7.66 out of 7.75 — because the catalog had enough lofi songs to actually differentiate on continuous features.

The scoring is fully transparent. Every recommendation comes with a breakdown showing exactly how many points each feature contributed. A user can see precisely why a song ranked where it did, which is something real streaming apps do not show.

The system also degrades gracefully. When given a genre that does not exist in the catalog (the Ghost Profile test), it did not crash or return random results. It fell back on mood and continuous features and still produced a coherent list.

---

## 6. Limitations and Bias

**Genre bonus creates a filter bubble for rare-genre users.**
12 out of 14 genres have only one song. Any user whose favorite genre is not lofi or pop will have exactly one song competing for the +2.00 genre bonus. That song wins the top spot automatically, no matter how poorly its other features match. In the All-Neutral experiment, Velvet Hours (r&b) ranked #1 with a 1.83 pt gap over #2 — entirely explained by the genre and mood bonus. The system locks rare-genre users into a single recommendation with no real competition.

**The catalog is skewed against rap and spoken-word listeners.**
16 out of 20 songs have a speechiness value below 0.10. A user targeting high speechiness (e.g., a rap fan) will find almost no close matches on that feature. Since speechiness is only worth 0.25 pts maximum, it barely moves the final score — but it means the feature cannot meaningfully serve that listener type.

**High-energy and low-energy users are not treated equally.**
The catalog's average energy is around 0.63, skewing high. Users who want very low energy (below 0.30) have fewer songs to match against, so their recommendations tend to score lower overall even when the math is working correctly.

---

## 7. Evaluation

Six user profiles were tested — three realistic and three adversarial.

The three standard profiles (Late-Night Studier, High-Energy Pop, Sunday Wind-Down) all produced #1 results that matched intuition. Focus Flow, Gym Hero, and Autumn Letter each won their respective lists cleanly, and the reasons shown for each confirmed the scoring was behaving as designed.

The three adversarial profiles revealed the system's limits. The Contradictory profile (blues/sad mood but energy target of 0.92) exposed that the categorical mood bonus always wins over the energy signal when they conflict — Blue Porch Night ranked #1 despite having the wrong energy, because its mood label alone was worth 1.50 pts. The Ghost Profile (classical/aggressive — no catalog match) showed the system degrades gracefully, falling back on continuous features to find tonally similar songs. The All-Neutral profile (r&b/romantic, all features at 0.5) confirmed the filter bubble: one genre match dominated the entire ranking.

A weight-shift experiment was also run: genre was halved to 1.00 pt and energy was doubled to 3.00 pts. The #1 result did not change for any profile — it just made the system more certain about existing winners rather than producing new variety. The original weights were restored.

---

## 8. Intended Use and Non-Intended Use

**Intended use:** This system is designed for classroom learning. It demonstrates how a content-based recommender works, how scoring rules translate preferences into numbers, and where biases show up in small datasets. It is a teaching tool, not a product.

**Not intended for:** Real users looking for actual music discovery. The catalog is too small and too narrow to serve real listeners. It should not be used to make decisions about what music gets promoted, since the catalog lacks cultural diversity and the scoring has no awareness of context, history, or community.

---

## 9. Ideas for Improvement

- **Expand the catalog significantly.** With only 1 song per genre for most genres, the genre bonus acts as an automatic winner. Adding 10–20 songs per genre would let the continuous features (energy, valence, tempo) do meaningful differentiation within genre — which is where the interesting recommendations actually come from.

- **Soften genre from binary to gradient.** Right now a genre match is worth 2.00 pts and a mismatch is worth 0.00 pts. A real improvement would score genre similarity on a spectrum — for example, folk and country are closer to each other than folk and metal. This would reduce the filter bubble effect for listeners whose taste spans adjacent genres.

- **Support multiple genres per user profile.** Every UserProfile holds exactly one favorite genre. A listener who genuinely enjoys both lofi for studying and synthwave for commuting cannot be represented. Supporting a list of genres with individual weights would make the system much more realistic.

---

## 10. Personal Reflection

**Biggest learning moment**

The biggest learning moment was the weight-shift experiment. I expected that halving the genre weight and doubling energy would shake up the rankings and surface different songs. Instead, the #1 result did not change for any of the six profiles. The songs that already matched on genre, mood, and energy just scored even higher — they did not face new competition. That taught me something I could not have reasoned out in advance: in a sparse catalog, weight tuning is almost meaningless. You need enough songs per category for different weights to actually compete. The algorithm was fine; the data was the ceiling.

**How AI tools helped — and when I had to check them**

AI tools were useful for generating the initial song catalog, drafting the scoring logic structure, and writing out the boilerplate dataclass fields. That saved real time. But I had to double-check two things closely. First, the ghost genre+mood combination: the morning runner profile originally used `mood="energetic"` with `genre="pop"`, but no such song existed in the catalog. The AI did not catch that — I had to spot it by running the code and seeing a suspiciously low score. Second, the tempo normalization: raw BPM values like 168 and 58 were outside the expected range and quietly produced out-of-bound scores. AI-generated code passed the tests I wrote for the normal cases but missed the edge cases. Writing adversarial tests was what caught it.

**What surprised me about simple algorithms "feeling" like recommendations**

The most surprising thing was how much the reason strings did the work. The scoring math itself is just subtraction and multiplication — nothing that "understands" music. But when the output prints "genre match (lofi) +2.00pts; mood match (focused) +1.50pts; energy: song=0.40, target=0.38 → +1.47pts," it feels like the system genuinely understood why Focus Flow was the right pick. The explanation created the illusion of reasoning. That made me think about how much of what feels "intelligent" in real apps is just the interface wrapping a much simpler operation underneath.

**What I would try next**

If I extended this project, the first thing I would do is expand the catalog to at least 10 songs per genre. Almost every limitation I found — the filter bubble, the forced #1, the useless rankings below the top spot — traces back to catalog size. The scoring logic held up well; the data just could not give it enough to work with. After that, I would experiment with making genre a gradient instead of a binary — scoring folk/country as closer to each other than folk/metal — to see if that produces more surprising and useful cross-genre recommendations for listeners whose taste does not fit cleanly into one box.
