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

          // 1. Prepariamo i dati
          const html = TextUtils.Serialize(body || "");
          const users = await payload.find({
            collection: Slugs.Users,
            where: { id: { in: tos.map((t: any) => t.value.id || t.value).join(",") } },
          });
          const usersEmails = users.docs.map((u: any) => u.email);

          // 2. Caccia al tesoro del Bus (Scansione dinamica)
          let bus: any = (payload as any).serviceBus; // Prova 1: Root

          if (!bus && payload.config?.custom) {
            const custom = payload.config.custom as any;
            // Prova 2: custom è un oggetto e ha il bus
            if (custom.serviceBus) bus = custom.serviceBus;
            // Prova 3: custom è un array e il bus è uno degli elementi
            else if (Array.isArray(custom)) {
              bus = custom.find((i) => i && typeof i.publish === "function");
            }
          }

          // Prova 4: Cerchiamo in extensions
          if (!bus && (payload as any).extensions) {
            const ext = (payload as any).extensions;
            const key = Object.keys(ext).find(k => ext[k] && typeof ext[k].publish === 'function');
            if (key) bus = ext[key];
          }

          // 3. Esecuzione
          if (bus && typeof bus.publish === "function") {
            console.log("!!! [OK] Bus trovato. Invio in corso...");
            await bus.publish("mzinga_events", "communications", {
              from: (payload as any).emailOptions?.fromAddress || "info@mzinga.it",
              subject,
              tos: usersEmails,
              html,
            });
          } else {
            console.error("!!! [ERRORE] Il Bus non esiste in questa istanza di Mzinga.");
            // Log di emergenza per vedere cosa c'è davvero dentro custom
            console.log("DEBUG CONFIG:", JSON.stringify(payload.config?.custom || "vuoto"));
          }

          return doc;
        } catch (err) {
          console.error("!!! [HOOK ERROR]:", err);
          return doc;
        }
      },
    ],
  },
  fields: [
    { name: "subject", type: "text", required: true },
    { name: "tos", type: "relationship", relationTo: [Slugs.Users], hasMany: true, required: true },
    { name: "sendToAll", type: "checkbox", label: "Send to all users?" },
    { name: "body", type: "richText", required: true },
  ],
};

export default Communications;