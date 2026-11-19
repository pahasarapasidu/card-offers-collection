// Credit Card Offers LK — mobile app (Android / iOS / web via Expo)
//
// Shows every scraped bank offer; the user picks the cards they own and the
// list filters to what applies to them. The app starts with the copy of
// offers.json bundled in assets/, then downloads the latest copy (refreshed
// daily by the GitHub Action) from OFFERS_URL.

import React, { useEffect, useMemo, useState } from "react";
import {
  AppState, Dimensions, Platform, FlatList, Linking, Modal, Pressable, SafeAreaView, ScrollView,
  StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from "react-native";
// expo-image decodes images by content, not by the server's (sometimes wrong)
// content-type header — Sampath serves JPEGs labelled application/octet-stream.
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import AsyncStorage from "@react-native-async-storage/async-storage";
import data from "./assets/offers.json";

// Palette: deep slate navy + royal blue brand, vibrant blue for
// interactive things, emerald for deals/savings (same as the website).
const NAVY = "#0F172A";
const BRAND = "#1E40AF";
const ACCENT = "#3B82F6";
const ACCENT_INK = "#1D4ED8";   // blue text on white
const ACCENT_SOFT = "#DBEAFE";
const DEAL = "#10B981";         // % off badges
const DEAL_INK = "#047857";     // emerald text on white
const TEXT = "#1E293B";
const MUTED = "#64748B";
const BORDER = "#E2E8F0";
const SOON_DAYS = 7;
const OFFERS_URL = "https://raw.githubusercontent.com/pahasarapasidu/card-offers-collection/main/data/offers.json";

// Some bank sites (e.g. Sampath) reject image requests that don't look like
// they come from a normal browser, so send browser-like headers.
const imgSource = (uri) => {
  // Browsers block cross-site image requests that carry custom headers (CORS),
  // and only the phone apps need them, so send a plain request on web.
  if (Platform.OS === "web") return { uri };
  const origin = (uri.match(/^https?:\/\/[^/]+/) || [""])[0];
  return {
    uri,
    headers: {
      "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
      "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
      "Referer": origin + "/",
    },
  };
};

const CARD_OPTIONS = [
  { key: "sampath-visa",       label: "Sampath Visa",       bank: "Sampath Bank",    network: "visa" },
  { key: "sampath-mastercard", label: "Sampath Mastercard", bank: "Sampath Bank",    network: "mastercard" },
  { key: "sampath-amex",       label: "Sampath Amex",       bank: "Sampath Bank",    network: "amex" },
  { key: "combank-visa",       label: "ComBank Visa",       bank: "Commercial Bank", network: "visa" },
  { key: "combank-mastercard", label: "ComBank Mastercard", bank: "Commercial Bank", network: "mastercard" },
  { key: "hnb-visa",           label: "HNB Visa",           bank: "HNB",             network: "visa" },
  { key: "hnb-mastercard",     label: "HNB Mastercard",     bank: "HNB",             network: "mastercard" },
  { key: "hnb-amex",           label: "HNB Amex",           bank: "HNB",             network: "amex" },
  { key: "seylan-visa",        label: "Seylan Visa",        bank: "Seylan Bank",     network: "visa" },
  { key: "seylan-mastercard",  label: "Seylan Mastercard",  bank: "Seylan Bank",     network: "mastercard" },
  { key: "ntb-visa",           label: "NTB Visa",           bank: "Nations Trust",   network: "visa" },
  { key: "ntb-mastercard",     label: "NTB Mastercard",     bank: "Nations Trust",   network: "mastercard" },
  { key: "ntb-amex",           label: "NTB Amex",           bank: "Nations Trust",   network: "amex" },
  { key: "boc-visa",           label: "BOC Visa",           bank: "BOC",             network: "visa" },
  { key: "boc-mastercard",     label: "BOC Mastercard",     bank: "BOC",             network: "mastercard" },
  { key: "ndb-visa",           label: "NDB Visa",           bank: "NDB",             network: "visa" },
  { key: "ndb-mastercard",     label: "NDB Mastercard",     bank: "NDB",             network: "mastercard" },
  { key: "peoples-visa",       label: "Peoples Visa",       bank: "Peoples Bank",    network: "visa" },
  { key: "peoples-mastercard", label: "Peoples Mastercard", bank: "Peoples Bank",    network: "mastercard" },
  { key: "dfcc-visa",          label: "DFCC Visa",          bank: "DFCC",            network: "visa" },
  { key: "dfcc-mastercard",    label: "DFCC Mastercard",    bank: "DFCC",            network: "mastercard" },
];

// Sort chips are toggles: tap the active one again to go back to the
// default (featured) order, so nothing looks permanently stuck on.
const SORTS = [
  { key: "ending",   label: "Ending soon" },
  { key: "discount", label: "Biggest %" },
];

/* ---------- date / discount helpers (same logic as the web app) ---------- */
const MONTHS = { january:0, february:1, march:2, april:3, may:4, june:5,
                 july:6, august:7, september:8, october:9, november:10, december:11 };

// Prefer the scraper's clean end_date (YYYY-MM-DD); older data only has text.
function parseEndDate(period, endDate) {
  if (endDate) {
    const d = new Date(endDate + "T23:59:59");
    if (!isNaN(d)) return d;
  }
  if (!period) return null;
  const iso = period.match(/\d{4}-\d{2}-\d{2}/g);
  if (iso) {
    const d = new Date(iso[iso.length - 1] + "T23:59:59");
    return isNaN(d) ? null : d;
  }
  const words = [...period.matchAll(/(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})/gi)];
  if (words.length) {
    const m = words[words.length - 1];
    return new Date(+m[3], MONTHS[m[2].toLowerCase()], +m[1], 23, 59, 59);
  }
  return null;
}

function discountLine(o) {
  if (o.discount) return o.discount;
  const m = (o.description || "").match(/(up to\s+)?\d{1,3}\s*%(\s*(discount|off))?/i);
  return m ? m[0].replace(/\s+/g, " ").trim() : "";
}

// Lower-case, accents removed ("Café" -> "cafe"), spaces collapsed.
function fold(s) {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ");
}

// Precompute sort/expiry/search fields once per dataset.
function prepareOffers(raw) {
  const now = new Date();
  const seen = new Set();  // ids must be unique: favourites and list keys use them
  return raw.offers.filter(o => !seen.has(o.id) && seen.add(o.id)).map(o => {
    const end = parseEndDate(o.period, o.end_date);
    // Whole days left after today: 0 = ends tonight. An offer whose end
    // (23:59:59 on its last day) has passed is expired.
    const days = end ? Math.floor((end - now) / 86400000) : null;
    const expired = end ? end < now : false;
    const pctM = (o.discount || o.description || "").match(/(\d{1,3})\s*%/);
    return {
      ...o,
      _end: end ? end.getTime() : null,
      _days: days,
      _soon: !expired && days !== null && days <= SOON_DAYS,
      _expired: expired,
      _pct: pctM ? +pctM[1] : 0,
      _d: discountLine(o),
      _search: fold([o.merchant, o.description, o.bank, o.category, o.city].join(" ")),
    };
  }).filter(o => !o._expired);
}

function makeDataset(raw) {
  return {
    raw,
    generatedAt: raw.generated_at,
    bankCount: raw.banks.length,
    offers: prepareOffers(raw),
  };
}

// Returns the latest offers.json from GitHub, or null if offline/unreachable.
async function downloadOffers() {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const res = await fetch(OFFERS_URL, { signal: ctrl.signal });
    if (!res.ok) return null;
    const raw = await res.json();
    return raw && Array.isArray(raw.offers) ? raw : null;
  } catch (e) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function formatUpdated(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/* ---------------------------- the app ---------------------------- */
export default function App() {
  const [myCards, setMyCards] = useState([]);
  const [favs, setFavs] = useState([]);
  const [cat, setCat] = useState("All");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("featured");
  const [selected, setSelected] = useState(null); // offer open in the modal
  const [dataset, setDataset] = useState(() => makeDataset(data));
  const [refreshing, setRefreshing] = useState(false);

  // Swap in the online copy if it's newer than what we're showing. Either
  // way, re-check expiry so offers that ended since last time drop out.
  const refreshOffers = async () => {
    const raw = await downloadOffers();
    setDataset(cur => makeDataset(raw && raw.generated_at > cur.generatedAt ? raw : cur.raw));
  };

  useEffect(() => {
    refreshOffers();
    // Phones keep apps alive in the background for days; refresh on return.
    const sub = AppState.addEventListener("change", s => { if (s === "active") refreshOffers(); });
    return () => sub.remove();
  }, []);

  const onPullRefresh = async () => {
    setRefreshing(true);
    await refreshOffers();
    setRefreshing(false);
  };

  const categories = useMemo(
    () => ["All", "♥ Saved", ...[...new Set(dataset.offers.map(o => o.category))].sort()],
    [dataset]
  );

  // Load saved cards/favourites once at startup.
  useEffect(() => {
    (async () => {
      try {
        const c = await AsyncStorage.getItem("coc-cards");
        const f = await AsyncStorage.getItem("coc-favs");
        // If the user already tapped something while this was loading,
        // keep their choice rather than overwriting it with the old list.
        if (c) setMyCards(cur => (cur.length ? cur : JSON.parse(c)));
        if (f) setFavs(cur => (cur.length ? cur : JSON.parse(f)));
      } catch (e) {}
    })();
  }, []);

  const toggleCard = (key) => {
    setMyCards(cur => {
      const next = cur.includes(key) ? cur.filter(k => k !== key) : [...cur, key];
      AsyncStorage.setItem("coc-cards", JSON.stringify(next)).catch(() => {});
      return next;
    });
  };
  const toggleFav = (id) => {
    setFavs(cur => {
      const next = cur.includes(id) ? cur.filter(k => k !== id) : [...cur, id];
      AsyncStorage.setItem("coc-favs", JSON.stringify(next)).catch(() => {});
      return next;
    });
  };

  // If a data refresh removed the chosen category, go back to "All".
  useEffect(() => {
    if (!categories.includes(cat)) setCat("All");
  }, [categories]);

  // Only count saved offers that still exist (old ones expire away).
  const savedCount = useMemo(
    () => dataset.offers.filter(o => favs.includes(o.id)).length,
    [dataset, favs]
  );

  const matchesCards = (o) => {
    if (myCards.length === 0) return true;
    for (const key of myCards) {
      const card = CARD_OPTIONS.find(c => c.key === key);
      if (!card || card.bank !== o.bank) continue;
      const networks = (o.card_types || []).filter(t => ["visa","mastercard","amex"].includes(t));
      if (networks.length === 0 || networks.includes(card.network)) return true;
    }
    return false;
  };

  const visible = useMemo(() => {
    // Every word typed must appear somewhere: "hnb pizza" finds HNB's pizza deals.
    const words = fold(query).trim().split(" ").filter(Boolean);
    let list = dataset.offers.filter(o =>
      matchesCards(o) &&
      (cat === "All" ? true : cat === "♥ Saved" ? favs.includes(o.id) : o.category === cat) &&
      (!words.length || words.every(w => o._search.includes(w)))
    );
    if (sort === "ending") list = [...list].sort((a, b) => (a._end ?? Infinity) - (b._end ?? Infinity));
    if (sort === "discount") list = [...list].sort((a, b) => b._pct - a._pct);
    return list;
  }, [dataset, myCards, favs, cat, query, sort]);

  const soonCount = visible.filter(o => o._soon).length;

  return (
    <SafeAreaView style={s.safe}>
      <StatusBar barStyle="light-content" backgroundColor={NAVY} />
      <FlatList
        data={visible}
        keyExtractor={o => o.id}
        initialNumToRender={8}
        maxToRenderPerBatch={8}
        windowSize={7}
        refreshing={refreshing}
        onRefresh={onPullRefresh}
        ListHeaderComponent={
          <Header
            dataset={dataset} categories={categories}
            myCards={myCards} toggleCard={toggleCard}
            cat={cat} setCat={setCat} favCount={savedCount}
            query={query} setQuery={setQuery}
            sort={sort} setSort={setSort}
            total={visible.length} soonCount={soonCount}
          />
        }
        ListEmptyComponent={<Text style={s.empty}>No offers match your cards and filters.</Text>}
        renderItem={({ item }) => (
          <OfferCard o={item} fav={favs.includes(item.id)}
            onPress={() => setSelected(item)} onFav={() => toggleFav(item.id)} />
        )}
        contentContainerStyle={{ paddingBottom: 40 }}
      />
      <OfferModal o={selected} onClose={() => setSelected(null)} />
    </SafeAreaView>
  );
}

/* ---------------------------- header ---------------------------- */
function Header({ dataset, categories, myCards, toggleCard, cat, setCat, favCount, query, setQuery, sort, setSort, total, soonCount }) {
  const updated = formatUpdated(dataset.generatedAt);
  return (
    <View>
      <LinearGradient colors={[NAVY, "#172554", BRAND, ACCENT]} locations={[0, 0.38, 0.74, 1]}
        start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.hero}>
        <View style={s.eyebrow}>
          <View style={s.dot} />
          <Text style={s.eyebrowText}>{updated ? `UPDATED ${updated.toUpperCase()}` : "UPDATED DAILY"}</Text>
        </View>
        <Text style={s.h1}>Credit Card <Text style={{ color: "#6EE7B7" }}>Offers LK</Text></Text>
        <Text style={s.heroSub}>
          Every card discount from Sri Lanka's banks — pick your cards, see only what's yours.
        </Text>
        <View style={s.statsRow}>
          <Stat n={dataset.offers.length} t="offers" />
          <Stat n={dataset.bankCount} t="banks" />
          <Stat n={categories.length - 2} t="categories" />
        </View>
      </LinearGradient>

      <Text style={s.label}>MY CARDS</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
        {CARD_OPTIONS.map(c => (
          <Chip key={c.key} on={myCards.includes(c.key)} label={c.label} onPress={() => toggleCard(c.key)} />
        ))}
      </ScrollView>

      <Text style={s.label}>CATEGORY</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
        {categories.map(c => (
          <Chip key={c} on={cat === c}
            label={c === "♥ Saved" && favCount ? `♥ Saved (${favCount})` : c}
            onPress={() => setCat(c)} />
        ))}
      </ScrollView>

      <TextInput
        style={s.search}
        placeholder="Search merchant — Pizza, Hotel, Keells…"
        placeholderTextColor="#94A3B8"
        value={query}
        onChangeText={setQuery}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
        {SORTS.map(x => (
          <Chip key={x.key} on={sort === x.key} label={x.label}
            onPress={() => setSort(sort === x.key ? "featured" : x.key)} />
        ))}
      </ScrollView>

      <Text style={s.count}>
        {total} offer{total === 1 ? "" : "s"}
        {myCards.length ? " for your cards" : " — select your cards to personalise"}
        {soonCount ? ` · ${soonCount} ending soon` : ""}
      </Text>
    </View>
  );
}

const Stat = ({ n, t }) => (
  <View style={s.stat}><Text style={s.statN}>{n}</Text><Text style={s.statT}>{t}</Text></View>
);

const Chip = ({ on, label, onPress }) => (
  <TouchableOpacity style={[s.chip, on && s.chipOn]} onPress={onPress}
    accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected: !!on }}>
    <Text style={[s.chipText, on && s.chipTextOn]}>{on ? "✓ " : ""}{label}</Text>
  </TouchableOpacity>
);

/* ---------------------------- offer card ---------------------------- */
function OfferCard({ o, fav, onPress, onFav }) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <Pressable style={s.card} onPress={onPress}
      // On web, role "button" becomes a <button>, which can't contain the ♡ button.
      accessibilityRole={Platform.OS === "web" ? undefined : "button"}
      accessibilityLabel={`${o.merchant}. ${o._d || ""}. ${o.bank}`}>
      <View style={s.thumbWrap}>
        {o.image_url && !imgFailed
          ? <Image source={imgSource(o.image_url)} style={s.thumb} contentFit="cover" cachePolicy="memory-disk"
              transition={150} onError={() => setImgFailed(true)} />
          : <View style={[s.thumb, s.thumbEmpty]}><Text style={s.thumbInitial}>{(o.merchant || "?").trim().charAt(0).toUpperCase()}</Text></View>}
        {o._soon && (
          <View style={s.soon}><Text style={s.soonText}>
            {o._days === 0 ? "Last day" : o._days === 1 ? "1 day left" : `${o._days} days left`}
          </Text></View>
        )}
        {!!o._d && <View style={s.badge}><Text style={s.badgeText} numberOfLines={1}>{o._d}</Text></View>}
        <TouchableOpacity style={[s.fav, fav && s.favOn]} onPress={onFav} hitSlop={8}
          accessibilityRole="button" accessibilityLabel={fav ? "Remove from saved" : "Save offer"}
          accessibilityState={{ selected: fav }}>
          <Text style={{ color: "#fff", fontSize: 15 }}>{fav ? "♥" : "♡"}</Text>
        </TouchableOpacity>
      </View>
      <View style={s.cardBody}>
        <Text style={s.merchant} numberOfLines={1}>{o.merchant}</Text>
        <Text style={s.desc} numberOfLines={2}>{o.description}</Text>
        <View style={s.tagRow}>
          <Text style={[s.tag, s.tagBank]}>{o.bank}</Text>
          <Text style={s.tag}>{o.category}</Text>
        </View>
      </View>
    </Pressable>
  );
}

/* ---------------------------- detail modal ---------------------------- */
function OfferModal({ o, onClose }) {
  if (!o) return null;
  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={s.modalBg}>
        <View style={s.modal}>
          <ScrollView contentContainerStyle={{ paddingBottom: 28 }}>
            {o.image_url && <Image source={imgSource(o.image_url)} style={s.modalImg} contentFit="cover" cachePolicy="memory-disk" />}
            <View style={{ padding: 18 }}>
              <Text style={s.modalTitle}>{o.merchant}</Text>
              {!!o._d && <Text style={s.modalDiscount}>{o._d}</Text>}
              <Text style={s.modalDesc}>{o.description}</Text>
              <View style={s.tagRow}>
                <Text style={[s.tag, s.tagBank]}>{o.bank}</Text>
                <Text style={s.tag}>{o.category}</Text>
                {!!o.period && <Text style={s.tag}>🗓 {o.period}</Text>}
                {!!o.city && <Text style={s.tag}>📍 {o.city}</Text>}
              </View>
              {!!o.details && <Section title="Offer details" body={o.details} />}
              {!!o.terms && <Section title="Terms & conditions" body={o.terms} />}
              <TouchableOpacity onPress={() => Linking.openURL(o.source_url)}>
                <Text style={s.link}>View on {o.bank} website →</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
          <TouchableOpacity style={s.close} onPress={onClose}>
            <Text style={{ color: "#fff", fontSize: 16 }}>✕</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

function Section({ title, body }) {
  const [open, setOpen] = useState(false);
  return (
    <View style={s.section}>
      <TouchableOpacity onPress={() => setOpen(!open)}>
        <Text style={s.sectionTitle}>{title} {open ? "–" : "+"}</Text>
      </TouchableOpacity>
      {open && <Text style={s.sectionBody}>{body}</Text>}
    </View>
  );
}

/* ---------------------------- styles ---------------------------- */
const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#F8FAFC" },
  hero: { padding: 20, paddingTop: 42, paddingBottom: 26 },
  eyebrow: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start",
    backgroundColor: "rgba(255,255,255,0.12)", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4, marginBottom: 12 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: "#34D399" },
  eyebrowText: { color: "#BFDBFE", fontSize: 10, fontWeight: "700", letterSpacing: 2 },
  h1: { color: "#fff", fontSize: 30, fontWeight: "800", letterSpacing: -0.5 },
  heroSub: { color: "rgba(255,255,255,0.85)", marginTop: 8, fontSize: 13, lineHeight: 19 },
  statsRow: { flexDirection: "row", gap: 8, marginTop: 16 },
  stat: { flexDirection: "row", alignItems: "baseline", gap: 5,
    backgroundColor: "rgba(255,255,255,0.10)", borderRadius: 10, paddingHorizontal: 12, paddingVertical: 7 },
  statN: { color: "#fff", fontWeight: "800", fontSize: 16 },
  statT: { color: "#DBEAFE", fontSize: 11 },

  label: { fontSize: 10, fontWeight: "700", color: MUTED, letterSpacing: 1.5, marginTop: 16, marginLeft: 16, marginBottom: 6 },
  chipRow: { paddingHorizontal: 16, gap: 8 },
  chip: { borderWidth: 1, borderColor: BORDER, backgroundColor: "#fff", borderRadius: 999,
    paddingHorizontal: 14, paddingVertical: 8 },
  chipOn: { backgroundColor: BRAND, borderColor: BRAND },
  chipText: { fontSize: 12.5, color: TEXT },
  chipTextOn: { color: "#fff", fontWeight: "700" },
  search: { marginHorizontal: 16, marginTop: 14, marginBottom: 10, backgroundColor: "#fff",
    borderWidth: 1, borderColor: BORDER, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14 },
  count: { color: MUTED, fontSize: 12, margin: 16, marginBottom: 8 },
  empty: { textAlign: "center", color: MUTED, marginTop: 48 },

  card: { backgroundColor: "#fff", borderRadius: 16, marginHorizontal: 16, marginBottom: 14,
    overflow: "hidden", elevation: 2, shadowColor: "#000", shadowOpacity: 0.07, shadowRadius: 8, shadowOffset: { width: 0, height: 3 } },
  thumbWrap: { position: "relative" },
  thumb: { width: "100%", aspectRatio: 16 / 9, backgroundColor: ACCENT_SOFT },
  thumbEmpty: { alignItems: "center", justifyContent: "center" },
  thumbInitial: { fontSize: 40, fontWeight: "800", color: ACCENT, opacity: 0.5 },
  badge: { position: "absolute", left: 10, bottom: 10, backgroundColor: DEAL,
    borderRadius: 8, paddingHorizontal: 9, paddingVertical: 4, maxWidth: "70%" },
  badgeText: { color: "#022C22", fontSize: 11.5, fontWeight: "700" },
  soon: { position: "absolute", left: 10, top: 10, backgroundColor: "#DC2626",
    borderRadius: 7, paddingHorizontal: 8, paddingVertical: 3 },
  soonText: { color: "#fff", fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
  fav: { position: "absolute", right: 10, top: 10, width: 32, height: 32, borderRadius: 16,
    backgroundColor: "rgba(0,0,0,0.45)", alignItems: "center", justifyContent: "center" },
  favOn: { backgroundColor: BRAND },
  cardBody: { padding: 12 },
  merchant: { fontSize: 15, fontWeight: "700", color: TEXT },
  desc: { fontSize: 12, color: MUTED, marginTop: 3, lineHeight: 17 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 9 },
  tag: { fontSize: 10, fontWeight: "600", color: MUTED, backgroundColor: "#F1F5F9",
    borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3, overflow: "hidden" },
  tagBank: { color: ACCENT_INK, backgroundColor: ACCENT_SOFT },

  modalBg: { flex: 1, backgroundColor: "rgba(15,23,42,0.6)", justifyContent: "flex-end" },
  // Fixed pixel height: percentage heights around a ScrollView break
  // scrolling on Android, so give the sheet a definite size.
  modal: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20,
    height: Math.round(Dimensions.get("window").height * 0.85), overflow: "hidden" },
  modalImg: { width: "100%", aspectRatio: 16 / 9 },
  modalTitle: { fontSize: 20, fontWeight: "800", color: TEXT },
  modalDiscount: { color: DEAL_INK, fontWeight: "800", fontSize: 15, marginTop: 4 },
  modalDesc: { fontSize: 13.5, color: TEXT, lineHeight: 20, marginTop: 10 },
  section: { marginTop: 14, borderTopWidth: 1, borderTopColor: BORDER, paddingTop: 10 },
  sectionTitle: { fontWeight: "700", fontSize: 13.5, color: TEXT },
  sectionBody: { fontSize: 12.5, color: MUTED, lineHeight: 19, marginTop: 8 },
  link: { color: ACCENT_INK, fontWeight: "700", marginTop: 16, fontSize: 13.5 },
  close: { position: "absolute", top: 12, right: 12, width: 32, height: 32, borderRadius: 16,
    backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center" },
});
