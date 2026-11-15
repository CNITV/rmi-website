# RMI 2026 Discord bot

Botul configurează singur cele două servere (**RMI 2026 Online** pentru traduceri și **RMI 2026 On-site**) și gestionează accesul.

## Ce face

| Comandă | Ce face |
| --- | --- |
| `/setup` | Creează rolurile, categoriile, canalele și permisiunile (idempotent, nu șterge nimic). |
| `/approve member role [country] [team] [name]` | Dă rolul și setează nickname-ul după naming convention. `country` și `team` sunt dropdown-uri (vezi mai jos). |
| `/revoke member` | Scoate rolurile → persoana nu mai vede nimic. |
| `/pending` | Lista celor care au intrat dar n-au încă rol. |

**„Two-factor” (aprobare manuală):** `@everyone` nu are nicio permisiune, iar canalele devin vizibile *doar* prin roluri. Cine intră nu vede nimic; botul anunță în `#join-requests` (admin-only), iar un admin rulează `/approve`.

### Roluri și naming convention

**Online (traduceri)** — canale: INFO, TRANSLATIONS, TEAM LEADERS, ISC (privat), Meeting rooms (voce ×4), ADMIN

| Rol | Nickname |
| --- | --- |
| Admin | `[ADMIN] Nume` |
| Scientific Committee | `[ISC] Livia Magureanu` |
| Team Leader | `[RO-TL] Livia Magureanu` |

**On-site** — canale: INFO (`announcements`, `general`, `q-and-a`, `arrivals`), VOLUNTEERS, ORGANIZERS, TEAM LEADERS, ADMIN

| Rol | Nickname |
| --- | --- |
| Admin | `[ADMIN] Nume` |
| Organizing Committee | `[ORG] Nume` |
| Volunteer | `[VOL] Nume` |
| Team Leader | `[RO-A1 TL] Nume` |
| Contestant | `[RO-A1] Nume` |

### Țară și echipă (dropdown)

La `/approve`, `country` și `team` sunt liste cu căutare (tastezi și se filtrează):
- **country**: doar țările înscrise, cu steag (🇷🇴 Romania). Pe serverul on-site apar doar țările care au echipe On-site.
- **team**: apare după ce ai ales țara și arată doar echipele ei (pe on-site, doar cele On-site), cu codul în paranteză: `Vianu 3 (V3)`.
- Se cer doar unde contează: Team Leader online → doar țara (`[RO-TL]`); Team Leader / Contestant on-site → țara și echipa (`[RO-V3 TL]`, `[RO-V3]`). Nu poți introduce o țară sau echipă care nu e în listă.

Lista vine din `data/participants_2026.csv` (aceeași ca pe pagina de participanți) și se re-citește singură: după un `git pull` și un `python scripts/generate_participants_2026.py --registrations ...` apar echipele noi, fără restart. Fișierul se poate schimba cu `RMI_TEAMS_CSV`.

Codul echipei se generează din nume (inițialele, cifrele păstrate, fără prefixul țării): `Vianu 3` → `V3`, `Romania Juniors 1` → `J1`, `Romania 1` → `1`, `Azerbaijan Team Girls` → `TG`. La coliziuni în aceeași țară se adaugă o literă. Coduri manuale: `TEAM_CODE_OVERRIDES` în `teams.py`. Dacă apare o țară nouă, adaug-o în `COUNTRY_CODES` (un test pică dacă lipsește).

Formatul on-site (țară + cod echipă) este o presupunere — se schimbă într-o linie, în `profiles.py`.

Reguli on-site: doar Admin/Organizing/Volunteer pot crea canale noi (au *Manage Channels*), `#announcements` e scriere doar pentru organizatori, voluntarii au canale separate. Nu există canale pe țară/echipă (deocamdată).

## Pornire (o singură dată)

1. **Creează aplicația** — https://discord.com/developers/applications → *New Application* → „RMI Bot”.
2. **Bot** (meniul din stânga): *Reset Token* → copiază token-ul (îl pui doar în `.env`, nu îl trimite nimănui). Activează **Server Members Intent**. Poți dezactiva *Public Bot*.
3. **Invită botul pe ambele servere** — înlocuiește `APP_ID` cu *Application ID* din *General Information*:
   `https://discord.com/oauth2/authorize?client_id=APP_ID&scope=bot%20applications.commands&permissions=8`
   (`permissions=8` = Administrator; e nevoie ca botul să poată crea roluri și canale cu orice permisiuni.)
4. În **Server Settings → Roles**, trage rolul botului **deasupra** oricăror roluri existente.
5. Rulează botul:
   ```bash
   cd discord-bot
   pip install -r requirements.txt
   cp .env.example .env     # pune DISCORD_TOKEN
   python bot.py
   ```
6. Pe fiecare server: `/setup` → dă-ți rolul **Admin** (ești owner, deci vezi tot oricum) → `/approve` pentru ceilalți.

> `/setup` scoate toate permisiunile lui `@everyone`: canalele create de Discord implicit (`#general`, etc.) devin invizibile pentru toți în afară de admini. Șterge-le după ce ai verificat că cele noi arată bine.
> Rularea repetată a `/setup` readuce permisiunile categoriilor/canalelor din profil la starea din `profiles.py` (modificările manuale pe ele se pierd).

## Găzduire

Botul trebuie să ruleze continuu (nu merge pe Netlify/Vercel). Orice VM mic, Raspberry Pi sau Railway/Fly.io/Render ca „worker”, cu `python bot.py` și `DISCORD_TOKEN` în variabile de mediu.

## Modificări

Canale, roluri, culori, prefixe: `profiles.py`. Teste: `python -m unittest discover -s tests`.
