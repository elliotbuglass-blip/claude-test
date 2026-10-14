// Seeds follower_snapshots with the readings the prototype banked.
// Usage: DATABASE_URL=... node scripts/seed-snapshots.mjs [file.json]
// Safe to re-run: upserts on day.
import fs from "node:fs";
import postgres from "postgres";

const file = process.argv[2] || new URL("../data/seed-snapshots.json", import.meta.url);
const rows = JSON.parse(fs.readFileSync(file, "utf8"));
if (!process.env.DATABASE_URL) { console.error("Set DATABASE_URL first."); process.exit(1); }

const sql = postgres(process.env.DATABASE_URL, { max: 1, prepare: false });
await sql`create table if not exists follower_snapshots (day date primary key, total integer not null)`;
for (const r of rows) {
  await sql`insert into follower_snapshots (day, total) values (${r.day}, ${r.total})
            on conflict (day) do update set total = excluded.total`;
}
console.log(`Seeded ${rows.length} days (${rows[0].day} → ${rows[rows.length - 1].day}).`);
await sql.end();
