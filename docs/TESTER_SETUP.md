# Giving a tester their own ReelBot

Each tester gets their **own copy** of ReelBot: their own web address, password, Instagram and reels.
Nothing is shared with your copy. It costs about $5 a month on Railway, plus their Claude usage on your key.

## Part 1 — once only: switch on the "Connect Instagram" button (you)

1. Go to **developers.facebook.com** → **My Apps** → your ReelBot app.
2. **App settings → Basic**: copy the **App ID** and the **App Secret** (press Show).
3. In Railway, open **your** ReelBot → **Variables** → add:
   - `META_APP_ID` = the App ID
   - `META_APP_SECRET` = the App Secret
4. Back in the Meta app: **Facebook Login → Settings → Valid OAuth Redirect URIs**. Add your address with
   `/connect/instagram/done` on the end. Settings → 📸 Instagram in ReelBot shows the exact address to copy.
5. If the left menu has no **Facebook Login**, add it: **Add product → Facebook Login → Set up**.
6. If your app shows **Facebook Login for Business** instead: open it → **Configurations → Create configuration**,
   tick the permissions `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`,
   `pages_show_list`, `pages_read_engagement`, `business_management`, then add its **Configuration ID** to Railway
   Variables as `META_LOGIN_CONFIG_ID`.

Never paste the App Secret into a chat; it only goes into Railway Variables.

## Part 2 — for each tester (you)

1. **Add them to the Meta app.** Meta app → **App roles → Roles → Add people → Testers** → type their Facebook name.
   They accept at **developers.facebook.com/requests** (they need a free Meta developer account for that).
   Until Meta approves the app, only people on this list can connect.
2. **Make their copy in Railway.**
   - Open your Railway project → **+ Create → GitHub Repo** → the same repo.
   - **Settings → Source → Branch**: the same branch as yours.
   - **Settings → Networking → Generate Domain** (their web address).
   - **Settings → Volumes → + Add volume**, mount path `/data` (start at 1GB; resize later if it fills up).
   - **Variables**:
     - `APP_PASSWORD` = a new password just for them
     - `ANTHROPIC_API_KEY` = your Claude key (or theirs)
     - `META_APP_ID`, `META_APP_SECRET` = same as yours
     - Leave out `IG_ACCESS_TOKEN`, `IG_USER_ID` and `APIFY_TOKEN`.
3. **Add their address to the Meta app** (Valid OAuth Redirect URIs), with `/connect/instagram/done` on the end.
4. Send them their web address and password.

## Part 3 — the tester

1. Their Instagram must be a **Creator or Business** account, linked to a **Facebook Page**
   (Instagram → Settings → Account type and tools; and Instagram → Accounts Centre to link the Page).
2. Open ReelBot → log in → **Settings → 📸 Instagram → Connect Instagram**. Log in with Facebook and tick
   their Page and Instagram when asked.
3. Still in **Settings**: fill in **About my account**, their **competitors** and **hashtags**. A new copy starts
   with Elliot's niche and competitors, so they must change these to their own.
4. Upload a couple of clips and use **Review** mode first.

## Updating

Every copy updates by itself when the branch is pushed, same as yours.
