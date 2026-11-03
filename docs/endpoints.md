# Endpoints

All details below are written from observed behaviour of the consumer app
(3.46.0) against a personal account. Values marked **live** were confirmed with
a real request/response. This documents only read operations.

## Conventions

- **Base URL:** `https://{service}.mywellness.com` — `core`, `workout`,
  `training`. Non-prod environments append `-dev` / `-test` / `-beta` before
  `.mywellness.com`.
- **Culture:** every request carries a `_c` query parameter (e.g. `_c=en`).
- **Headers (all requests):**
  - `Content-Type: application/json`
  - `x-mwapps-client: tgappandroidcoach`
  - `x-mwapps-appid: EC1D38D7-D359-48D0-A60C-D8C0B8FB9DF9`
  - `x-mwapps-clientversion: 3.46.0.3444,tgappandroidcoach` — format is
    `<versionName>.<versionCode>,<client>`
  - `x-mwapps-pdate: <YYYYMMDD>` (the current date)
  - `x-mwapps-tz-olson: <Olson timezone>`
- **Auth:** after login, add `Authorization: Bearer <token>`.

> The app id and the client-version **format** matter: an unrecognised app
> identity makes the server return `401` with an empty body *before* checking
> credentials. With the correct identity, invalid credentials instead return
> `401 {"result": "UsernameOrPasswordNotValid"}`.

## Authentication — login (live)

```
POST https://core.mywellness.com/v2/enduser/authentication/Login?_c=en
Content-Type: application/json

{
  "username": "<email>",
  "password": "<password>",
  "domain": "com.mywellness",
  "keepMeLoggedIn": true
}
```

**200 response** (abridged):

```json
{
  "accountConfirmed": true,
  "result": "Success",
  "token": "<bearer token>",
  "userContext": {
    "id": "<uuid>",
    "accountUsername": "<email>",
    "firstName": "...",
    "lastName": "...",
    "nickName": "...",
    "gender": "M|F",
    "birthDate": "YYYYMMDD",
    "measurementSystem": "Metric|Imperial",
    "defaultCulture": "tr-TR",
    "timeZoneWindowsId": "Turkey Standard Time",
    "createdOn": "2026-...Z"
  },
  "facilities": []
}
```

The response also echoes the token in an `Authorization: Bearer <token>` header.

**Errors:** `401` empty → wrong app identity/headers. `401 {"result":
"UsernameOrPasswordNotValid"}` → bad credentials.

## Profile (live)

The account profile is the `userContext` object of the login response; no
separate call is required for the basic profile.

## Workout history — list (live)

```
GET https://workout.mywellness.com/v2/enduser/workout/GetUserWorkouts
    ?_c=en&from=YYYYMMDD&to=YYYYMMDD
Authorization: Bearer <token>
```

- **Dates** use the `YYYYMMDD` format. Other formats return `400` with a
  per-field validation message.
- **200 response** envelope:

```json
{ "from": "YYYYMMDD", "to": "YYYYMMDD", "items": [ ... ], "totalCount": 0 }
```

- `totalCount` is the number of matching workouts; `items` is the page of
  results. Additional query parameters observed in the app (`SearchFilterText`,
  `SessionTypes`, `SortField`, `SortOrder`) are not yet documented with verified
  values here.

## Performed-workout history — logbook (live)

The actual list of workouts the account performed (machine sessions, etc.):

```
GET https://workout.mywellness.com/logbook?desiredSize=50&ignoreType=Lifestyle&_c=en-US
Authorization: Bearer <token>
```

> Note this path has **no** `/v2/enduser` prefix.

**200 response:**

```json
{
  "data": { "logbooks": [
    {
      "id": "9001", "idCr": 9001,
      "title": "Free training", "type": "GenericWorkout",
      "performedOn": "2026-06-01 12:00:00 +03:00", "partitionDate": 20260601,
      "calories": 500, "move": 400, "duration": 3000,
      "totalExeDone": 2, "equipmentName": "Run Artis",
      "pictureUrl": "https://cdnmedia.mywellness.com/..."
    }
  ] },
  "token": "...", "version": 1, "currentUtcTimestamp": 0
}
```

`duration` is in seconds; `move` is the Technogym MOVE metric. `GetUserWorkouts`
(above) lists *saved workout templates*, which is different from this history.

## Workout create / delete (live, write)

```
PUT https://workout.mywellness.com/v2/enduser/workout?_c=en
Authorization: Bearer <token>
{ "name": "...", "assignedInFacilityId": null, "displayWorkoutId": "<client uuid>" }
-> 200 { "displayWorkoutId": "U-<hex>" }     # the server-assigned id

GET  https://workout.mywellness.com/v2/enduser/workout/{id}      # overview

DELETE https://workout.mywellness.com/v2/enduser/workout?_c=en
Authorization: Bearer <token>
{ "workoutId": "U-<hex>" }                   # id goes in the BODY, not the path
-> 200 {}
```

Deleting via `DELETE /v2/enduser/workout/{id}` (id in path) returns `405`; the id
must be in the body.

## Not yet implemented / to verify

- Workout/session **detail** (per-exercise sets, cardio samples, heart-rate series).
- `addPhysicalActivity` (adding exercises to a workout with a nested
  `prescribedPhysicalActivity`), and training-program create/assign/week-plan.
- Exact pagination/sort parameters for `GetUserWorkouts`.
