# Instagram Webhook Privacy Page Design

**Date:** 2026-07-30

## Goal

Publish a public English privacy policy for Building Intent Social Publish at:

`https://building-intent-instagram-webhook.cwsbrian.workers.dev/privacy`

The policy must describe the deployed Instagram comment keyword and private
reply system as it actually operates.

## Scope

The existing Cloudflare Worker will serve a static HTML page for `GET
/privacy`. No separate site, framework, analytics, cookies, form, or additional
storage will be added.

## Disclosures

The page will state that the service:

* receives Instagram comment IDs, media IDs, usernames where supplied, and
  comment text through Meta webhooks;
* uses comment text only to compare it with the approved keyword and does not
  store the comment text or username;
* stores media-specific reply rules, comment IDs used for duplicate
  prevention, delivery status, and Meta message IDs;
* uses the data to send the requested information and relevant App Store link,
  prevent duplicate replies, secure the service, and troubleshoot failures;
* processes data through Meta and Cloudflare and does not sell personal data or
  share it for third-party advertising;
* retains stored identifiers and delivery records only as needed to operate
  the service and honor duplicate prevention, subject to deletion requests;
* accepts access or deletion requests at `buildingintent@gmail.com`;
* may update the policy and displays its effective date.

The page will link to Meta's and Cloudflare's own privacy policies. It will not
claim compliance certification or provide legal guarantees.

## Rendering and Security

The response will be a self-contained, readable HTML document with UTF-8
content and no client-side JavaScript or third-party assets. Other methods on
`/privacy` will continue to return the existing not-found response.

## Verification

An automated Worker test will verify that `GET /privacy` returns HTML with:

* HTTP 200;
* the Building Intent Social Publish name;
* the effective date;
* the public contact email;
* data collection, use, retention, sharing, and deletion sections.

After deployment, a live request will verify that the public URL returns HTTP
200 and the expected page title.
