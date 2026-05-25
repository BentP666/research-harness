/* global Components, Services, Zotero, APP_SHUTDOWN */

var chromeHandle;

function install(data, reason) {}

async function startup({ rootURI }, reason) {
  const aomStartup = Components.classes[
    "@mozilla.org/addons/addon-manager-startup;1"
  ].getService(Components.interfaces.amIAddonManagerStartup);
  const manifestURI = Services.io.newURI(rootURI + "manifest.json");
  chromeHandle = aomStartup.registerChrome(manifestURI, [
    ["content", "researchharnesszotero", rootURI + "content/"],
    ["locale", "researchharnesszotero", "en-US", rootURI + "locale/en-US/"],
    ["locale", "researchharnesszotero", "zh-CN", rootURI + "locale/zh-CN/"]
  ]);

  const scope = { rootURI };
  scope.globalThis = scope;
  Services.scriptloader.loadSubScript(
    rootURI + "content/rh-zotero-panel.js",
    scope
  );
  await scope.RHZoteroPanel.startup(rootURI);
}

async function onMainWindowLoad({ window }, reason) {
  await Zotero.RHZoteroPanel?.onMainWindowLoad(window);
}

async function onMainWindowUnload({ window }, reason) {
  await Zotero.RHZoteroPanel?.onMainWindowUnload(window);
}

async function shutdown({ id, version, resourceURI, rootURI }, reason) {
  if (reason === APP_SHUTDOWN) {
    return;
  }
  await Zotero.RHZoteroPanel?.shutdown();
  if (chromeHandle) {
    chromeHandle.destruct();
    chromeHandle = null;
  }
}

function uninstall(data, reason) {}
