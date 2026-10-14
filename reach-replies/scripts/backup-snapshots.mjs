// Prints follower_snapshots as JSON. This table can't be rebuilt — Instagram
// won't give the history back — so keep a copy somewhere else.
// Usage: DATABASE_URL=... node scripts/backup-snapshots.mjs > backup.json
import postgres from "postgres";

const sql = postgres(process.env.DATABASE_URL, { max: 1, prepare: false });
const rows = await sql`select to_char(day, 'YYYY-MM-DD') as day, total from follower_snapshots order by day`;
console.log(JSON.stringify(rows.map((r) => ({ day: r.day, total: r.total })), null, 2));
await sql.end();
