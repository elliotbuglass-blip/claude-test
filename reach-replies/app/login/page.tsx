export const metadata = { title: "Sign in · Reach & Replies" };

export default async function Login({ searchParams }: { searchParams: Promise<{ wrong?: string }> }) {
  const { wrong } = await searchParams;
  return (
    <main className="login">
      <form method="post" action="/api/login">
        <h1>Reach &amp; Replies</h1>
        <p>Private. Enter the password to carry on.</p>
        <label className="eyebrow" htmlFor="pw">Password</label>
        <input id="pw" name="password" type="password" autoComplete="current-password" autoFocus required />
        {wrong ? <p className="wrong">That password didn&rsquo;t match.</p> : null}
        <button className="act primary" type="submit">Sign in</button>
      </form>
    </main>
  );
}
