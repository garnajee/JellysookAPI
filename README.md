# JellysookAPI

Flask API for gathering and sending Jellyseerr webhook data to any API.

Here is the code you need to put in Jellyseerr: `settings/notifications/webhook` :

```json
{
  "media_type": "{{media_type}}",
  "tmdbid": "{{media_tmdbid}}",
  "tvdbid": "{{media_tvdbid}}",
  "requestedBy_username": "{{requestedBy_username}}"
}
```

# Todo

- [x] check if it's a season or an episode -> **Check if it works (probably not)**

