export const DEPARTMENTS = {
  Audio: {
    headline: "Turn up your everyday",
    description: "Sound for work, play, and everything between.",
    items: [
      ["headphones", "Studio headphones"],
      ["speaker", "Pocket speaker"],
      ["earbuds", "Wireless earbuds"],
      ["record-player", "Record player"],
    ],
  },
  Workspace: {
    headline: "Upgrade your workspace",
    description: "Small upgrades. A better workday.",
    items: [
      ["lamp", "Task lamp"],
      ["keyboard", "Mechanical keyboard"],
      ["organizer", "Canvas organizer"],
      ["clock", "Desk clock"],
    ],
  },
  Home: {
    headline: "Make home your favorite place",
    description: "Considered essentials for your everyday.",
    items: [
      ["kettle", "Pour-over kettle"],
      ["mug", "Ceramic mug"],
      ["throw", "Linen throw"],
      ["shelf", "Oak shelf"],
    ],
  },
  Outdoors: {
    headline: "Ready for your next adventure",
    description: "Find your next reason to get outside.",
    items: [
      ["backpack", "Trail backpack"],
      ["bottle", "Steel water bottle"],
      ["lantern", "Camping lantern"],
      ["blanket", "Picnic blanket"],
    ],
  },
  Wellness: {
    headline: "A little time for yourself",
    description: "Everyday finds for feeling good.",
    items: [
      ["yoga-mat", "Yoga mat"],
      ["diffuser", "Travel diffuser"],
      ["sleep-mask", "Sleep mask"],
      ["fitness-band", "Fitness band"],
    ],
  },
};
export function productImage(product) {
  if (product.id?.startsWith("demo-")) {
    const match = Object.values(DEPARTMENTS)
      .flatMap(department => department.items)
      .find(([, name]) => product.title?.toLowerCase().startsWith(name.toLowerCase()));
    if (match) return "/products/store/" + match[0] + ".svg";
  }
  const source = typeof product.image === "string" ? product.image.trim() : "";
  // Old research imports used decorative SVGs when their source had no photo.
  // A missing source photo must remain visibly missing, not become a fake product.
  if (!source || (!product.id?.startsWith("demo-") && /^\/products\/.*\.svg(?:\?|$)/i.test(source)))
    return null;
  if (source.startsWith("/") && !source.startsWith("//")) return source;
  try {
    const url = new URL(source);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}
export function departmentProduct(category, demo = false) {
  const actual =
    category.preview_items?.find(product => productImage(product)) || category.preview_items?.[0];
  if (actual) return actual;
  const example = demo && DEPARTMENTS[category.name]?.items[0];
  return example
    ? {
        id: "demo-category-" + category.name,
        title: example[1],
        image: "/products/store/" + example[0] + ".svg",
      }
    : { title: category.name };
}
