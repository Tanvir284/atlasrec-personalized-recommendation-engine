import "./globals.css";
import { Providers, Shell } from "../components/ui";
export const metadata = {
  title: "AtlasRec — Find your everyday favorites",
  description:
    "Explore everyday essentials, save your favorites, and discover products recommended for your interests.",
};
const EXTENSION_SANITIZER_SCRIPT = `(function(){try{var B=/^(bis_skin_checked|bis_register|__bis_.*|data-gr-ext-installed|data-new-gr-c-s-check-loaded|cz-shortcut-listen)$/i;var s=Element.prototype.setAttribute;Element.prototype.setAttribute=function(n,v){if(B.test(n))return;return s.call(this,n,v);};function c(r){if(!r||!r.querySelectorAll)return;var els=r.querySelectorAll("[bis_skin_checked],[bis_register],[cz-shortcut-listen]");for(var i=0;i<els.length;i++){els[i].removeAttribute("bis_skin_checked");els[i].removeAttribute("bis_register");els[i].removeAttribute("cz-shortcut-listen");}}c(document.documentElement);var mo=new MutationObserver(function(ms){for(var i=0;i<ms.length;i++){var m=ms[i];if(m.type==="attributes"&&B.test(m.attributeName)&&m.target){m.target.removeAttribute(m.attributeName);}else if(m.type==="childList"){c(m.target);}}});mo.observe(document.documentElement,{attributes:true,childList:true,subtree:true});window.addEventListener("load",function(){setTimeout(function(){mo.disconnect();},2500);},{once:true});}catch(_){}})();`;

export default function Layout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: EXTENSION_SANITIZER_SCRIPT }} />
      </head>
      <body suppressHydrationWarning>
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
