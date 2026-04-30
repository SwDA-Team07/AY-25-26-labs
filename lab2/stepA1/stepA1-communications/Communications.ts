import { CollectionConfig } from "mzinga/types";
import { AccessUtils } from "../utils";
import { CollectionUtils } from "../utils/CollectionUtils";
import { TextUtils } from "../utils/TextUtils";
import { Slugs } from "./Slugs";

const access = new AccessUtils();
const collectionUtils = new CollectionUtils(Slugs.Communications);

const Communications: CollectionConfig = {
  slug: Slugs.Communications,
  access: {
    read: access.GetIsAdmin,
    create: access.GetIsAdmin,
    delete: access.GetIsAdmin,
    update: access.GetIsAdmin,
  },
  admin: {
    ...collectionUtils.GeneratePreviewConfig(),
    useAsTitle: "subject",
    group: "Notifications",
  },
  hooks: {
    afterChange: [
      async ({ doc, req: { payload } }) => {
        try {
          const { tos, subject, body } = doc;

          // 1. Data preparation and Email resolution
          const html = TextUtils.Serialize(body || "");
          
          // Extract User IDs ensuring compatibility with both raw IDs and nested objects
          const userIds = (tos || []).map((t: any) => t.value?.id || t.value);

          // Fetch user documents to get email addresses
          const users = await payload.find({
            collection: Slugs.Users,
            // Pass the array directly: Payload requires an array for the 'in' operator
            where: { id: { in: userIds } },
          });
          
          const usersEmails = users.docs.map((u: any) => u.email);

          // 2. Dynamic Service Bus Discovery (Discovery Pattern)
          // We search for the bus instance in different possible locations within the payload object
          let bus: any = (payload as any).serviceBus; 

          if (!bus && payload.config?.custom) {
            const custom = payload.config.custom as any;
            // Case A: Bus is directly in custom object
            if (custom.serviceBus) {
              bus = custom.serviceBus;
            } 
            // Case B: Custom is an array (middleware/plugins), find the item with a publish function
            else if (Array.isArray(custom)) {
              bus = custom.find((i) => i && typeof i.publish === "function");
            }
          }

          // Case C: Check payload extensions
          if (!bus && (payload as any).extensions) {
            const ext = (payload as any).extensions;
            const key = Object.keys(ext).find(k => ext[k] && typeof ext[k].publish === 'function');
            if (key) bus = ext[key];
          }

          // 3. Execution: Publish event to Message Bus
          if (bus && typeof bus.publish === "function" && usersEmails.length > 0) {
            console.log(`[Communications Hook] Bus found. Publishing notification to ${usersEmails.length} recipients.`);
            
            await bus.publish("mzinga_events", "communications", {
              from: (payload as any).emailOptions?.fromAddress || "info@mzinga.it",
              subject,
              tos: usersEmails,
              html,
            });
          } else if (usersEmails.length === 0) {
            console.warn("[Communications Hook] No valid recipients found. Skipping publish.");
          } else {
            console.error("[Communications Hook] Service Bus not found or not configured in this instance.");
          }

          return doc;
        } catch (err) {
          console.error("[Communications Hook Error]:", err);
          return doc;
        }
      },
    ],
  },
  fields: [
    { 
      name: "subject", 
      type: "text", 
      required: true 
    },
    { 
      name: "tos", 
      type: "relationship", 
      relationTo: [Slugs.Users], 
      hasMany: true, 
      required: true 
    },
    { 
      name: "sendToAll", 
      type: "checkbox", 
      label: "Send to all users?" 
    },
    { 
      name: "body", 
      type: "richText", 
      required: true 
    },
    {
      name: "status",
      type: "select",
      defaultValue: "pending",
      options: [
        { label: "Pending", value: "pending" },
        { label: "Processing", value: "processing" },
        { label: "Sent", value: "sent" },
        { label: "Failed", value: "failed" },
      ],
      admin: {
        position: "sidebar",
        description: "The current delivery status of this communication"
      }
    },
  ],
};

export default Communications;