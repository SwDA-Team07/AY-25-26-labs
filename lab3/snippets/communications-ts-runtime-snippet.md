# Communications.ts Runtime Snippet (Mirrored for Lab3 Evidence)

This snippet mirrors the local runtime changes used in `mzinga-apps/src/collections/Communications.ts`.
It is kept here as Lab3 evidence so no push is required to the `mzinga-apps` repo.

## Access + Admin Columns

```ts
access: {
  read: access.GetIsAdmin,
  create: access.GetIsAdmin,
  delete: () => {
    return false;
  },
  update: access.GetIsAdmin,
},
admin: {
  ...collectionUtils.GeneratePreviewConfig(),
  useAsTitle: "subject",
  defaultColumns: ["subject", "status", "tos"],
  group: "Notifications",
  disableDuplicate: true,
  enableRichTextRelationship: false,
},
```

## External Worker Hook Guard

```ts
hooks: {
  afterChange: [
    async ({ doc, operation }) => {
      if (process.env.COMMUNICATIONS_EXTERNAL_WORKER === "true") {
        const communicationId = doc?.id || doc?._id;
        // set pending only on create, do not reset worker updates
        if (operation === "create" && communicationId && doc.status !== "pending") {
          await payload.update({
            collection: Slugs.Communications,
            id: communicationId,
            data: { status: "pending" },
          });
        }
        return doc;
      }

      // fallback path unchanged
    },
  ],
},
```

## Status Field

```ts
{
  name: "status",
  type: "select",
  options: [
    { label: "Pending", value: "pending" },
    { label: "Processing", value: "processing" },
    { label: "Sent", value: "sent" },
    { label: "Failed", value: "failed" },
  ],
  admin: {
    readOnly: true,
    position: "sidebar",
  },
},
```
