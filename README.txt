DESKTOP HAMSTER

A small low-poly hamster that roams around your whole screen. Feed it,
pet it, let it nap.

INSTALL ON UBUNTU
  1. Put this folder anywhere (e.g. Downloads).
  2. Open a terminal in the folder and run:   bash install.sh
  3. Search "Desktop Hamster" in the app grid and launch it.
  Clicking the app icon again while it's running doesn't make a second hamster;
  the one you have says hi (and comes back if it was hidden).

TEST ON A MAC
  1. Unzip, open Terminal, and cd into the folder
     (type "cd " then drag the folder onto the Terminal window, press Enter).
  2. Run:   bash run_mac.sh
     The first run takes about a minute to download PyQt6. If macOS asks to
     install developer tools, accept and run the command again afterwards.
  3. Quit with right-click (two-finger click) -> Say goodbye.

CONTROLS
  Click            pet it (hearts, +joy)
  Click and drag   pick it up and set it down anywhere
  Mouse nearby     it looks at the cursor and sometimes follows it
  Shake the mouse  right next to it: it gets startled and scurries away
  Right-click      menu:
                     Feed > raspberries / mushroom / carrot
                     Pet
                     Go to sleep / Wake up
                     How are you?     (food / joy / rest bars, days together)
                     Say something
                     Party hat        (appears after 7 days together)
                     Names > rename the hamster / what it calls you
                     Read the note again
                     Hide for a while > 30 min / 1 hour / 2 hours
                     Quiet mode       (stops the idle chatter)
                     Start on login   (Linux only)
                     Say goodbye (quit)

HOW IT WORKS
  - First launch: it says hi, reads your note (message.txt), then asks what to
    call you.
  - It talks every minute or so. What it says depends on its mood, the time of
    day, how chubby it is, and how long you've had it; some lines use your name.
    It grooms, stretches, and slumps when it's sad.
  - Food drops near it; it walks over and eats with its cheeks stuffed.
  - Hunger drains over ~2 hours. When hungry it shows a raspberry bubble and
    walks slower, and its joy drops faster. Low joy = sad posture.
  - Rest runs down while awake; below 20% it curls up and sleeps on its own.
  - Chubbiness: feeding it when it's already full (food above 80) makes it
    rounder, in two stages. Walking around slowly slims it back down. Round
    hamsters waddle slower.
  - Days together: new lines unlock over time, and on milestone days
    (day 2, 4, 8, 15, 31, 51, 101, ...) it celebrates. From one week on it wears
    a party hat on those days, and you can put the hat on any time from the menu.
  - It hides itself while a fullscreen app is focused (video, game) and comes
    back after.
  - Stats are saved, and time passes while the app is closed (it never drops
    to fully starving while you're away).
  - Save file: ~/.config/desktop-hamster/state.json. It is kept apart from the
    app's files, so updating or reinstalling keeps the same hamster.

UPDATES
  The hamster updates itself from the GitHub repo named in UPDATE_REPO at the
  top of hamster.py. It checks about 20 s after launch (at most once every 20
  hours) and from right-click -> Check for updates. When there's a new version
  it downloads it, test-runs it without a screen, swaps the files, restarts,
  and says "i learned new tricks!" plus the notes. Name, days together, stats,
  chubbiness and hat all carry over. message.txt on her laptop is never
  overwritten. A version that fails its test run is not installed.

  To publish an update:
    1. Change the files (hamster.py, sprites/, ...).
    2. Raise "version" in version.json by 1 and write the "notes" (one speech
       bubble per line; {you} becomes her name).
    3. Commit and push to the main branch.
  A copy of the folder that contains .git (your working copy) never updates
  itself.

KNOWN LIMITS ON UBUNTU'S DEFAULT (WAYLAND) SESSION
  Ubuntu doesn't let apps see the mouse or other windows everywhere on Wayland.
  The mouse reactions and fullscreen hiding work with some apps (ones that run
  through XWayland, like most games and Chrome) but not all (e.g. Firefox and
  GNOME's own apps). If it covers something, right-click -> Hide for a while.
  On an "Ubuntu on Xorg" session (gear icon on the login screen, if offered),
  both work everywhere. On a Mac they work everywhere.

FILES
  hamster.py          the app
  message.txt         the note it reads on first launch
  version.json        version number + what the hamster says after updating
  sprites/            pre-rendered animation frames (keep next to hamster.py)
  build_sprites.py    optional: re-renders sprites/ if you want to change the look
                      (needs numpy + Pillow: pip install numpy pillow)

UNINSTALL (Ubuntu)
  rm -rf ~/.local/share/desktop-hamster
  (add  rm -rf ~/.config/desktop-hamster  to also erase the hamster's progress)
  rm ~/.local/share/applications/desktop-hamster.desktop
  rm -f ~/.config/autostart/desktop-hamster.desktop
