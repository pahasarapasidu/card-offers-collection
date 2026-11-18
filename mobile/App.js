// Card Offers Collection — mobile app (Android / iOS / web via Expo)
//
// Shows every scraped bank offer; the user picks the cards they own and the
// list filters to what applies to them. The app starts with the copy of
// offers.json bundled in assets/, then downloads the latest copy (refreshed
// daily by the GitHub Action) from OFFERS_URL.

import React, { useEffect, useMemo, useState } from "react";
import {
  Dimensions, FlatList, Linking, Modal, Pressable, SafeAreaView, ScrollView,
  StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from "react-native";
// expo-image decodes images by content, not by the server's (sometimes wrong)
// content-type header — Sampath serves JPEGs labelled application/octet-stream.
import { Image } from "expo-image";
import AsyncStorage from "@react-native-async-storage/async-storage";
import data from "./assets/offers.json";

const ACCENT = "#e8600a";
const SOON_DAYS = 7;
const OFFERS_URL = "https://raw.githubusercontent.com/pahasarapasidu/card-offers-collection/main/data/offers.json";

// Some bank sites (e.g. Sampath) reject image requests that don't look like
// they come from a normal browser, so send browser-like headers.
const imgSource = (uri) => {
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

// Precompute sort/expiry fields once per dataset.
function prepareOffers(raw) {
  const now = new Date();
  return raw.offers.map(o => {
    const end = parseEndDate(o.period, o.end_date);
    const days = end ? Math.ceil((end - now) / 86400000) : null;
    const pctM = (o.discount || o.description || "").match(/(\d{1,3})\s*%/);
    return {
      ...o,
      _end: end ? end.getTime() : null,
      _days: days,
      _soon: days !== null && days >= 0 && days <= SOON_DAYS,
      _expired: days !== null && days < 0,
      _pct: pctM ? +pctM[1] : 0,
      _d: discountLine(o),
    };
  }).filter(o => !o._expired);
}

function makeDataset(raw) {
  return {
    generatedAt: raw.generated_at,
    offerCount: raw.offer_count,
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

  // Swap in the online copy if it's newer than what we're showing.
  const refreshOffers = async () => {
    const raw = await downloadOffers();
    if (raw) {
      setDataset(cur => (raw.generated_at > cur.generatedAt ? makeDataset(raw) : cur));
    }
  };

  useEffect(() => { refreshOffers(); }, []);

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
        if (c) setMyCards(JSON.parse(c));
        if (f) setFavs(JSON.parse(f));
      } catch (e) {}
    })();
  }, []);

  const toggleCard = (key) => {
    const next = myCards.includes(key) ? myCards.filter(k => k !== key) : [...myCards, key];
    setMyCards(next);
    AsyncStorage.setItem("coc-cards", JSON.stringify(next)).catch(() => {});
  };
  const toggleFav = (id) => {
    const next = favs.includes(id) ? favs.filter(k => k !== id) : [...favs, id];
    setFavs(next);
    AsyncStorage.setItem("coc-favs", JSON.stringify(next)).catch(() => {});
  };

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
    const q = query.toLowerCase();
    let list = dataset.offers.filter(o =>
      matchesCards(o) &&
      (cat === "All" ? true : cat === "♥ Saved" ? favs.includes(o.id) : o.category === cat) &&
      (!q || o.merchant.toLowerCase().includes(q) || o.description.toLowerCase().includes(q))
    );
    if (sort === "ending") list = [...list].sort((a, b) => (a._end ?? Infinity) - (b._end ?? Infinity));
    if (sort === "discount") list = [...list].sort((a, b) => b._pct - a._pct);
    return list;
  }, [dataset, myCards, favs, cat, query, sort]);

  const soonCount = visible.filter(o => o._soon).length;

  return (
    <SafeAreaView style={s.safe}>
      <StatusBar barStyle="light-content" backgroundColor="#21130a" />
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
            cat={cat} setCat={setCat} favCount={favs.length}
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
      <View style={s.hero}>
        <View style={s.eyebrow}>
          <View style={s.dot} />
          <Text style={s.eyebrowText}>{updated ? `UPDATED ${updated.toUpperCase()}` : "UPDATED DAILY"}</Text>
        </View>
        <Text style={s.h1}>Card Offers <Text style={{ color: "#ffb36b" }}>Collection</Text></Text>
        <Text style={s.heroSub}>
          Every card discount from Sri Lanka's banks — pick your cards, see only what's yours.
        </Text>
        <View style={s.statsRow}>
          <Stat n={dataset.offerCount} t="offers" />
          <Stat n={dataset.bankCount} t="banks" />
          <Stat n={categories.length - 2} t="categories" />
        </View>
      </View>

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
        placeholderTextColor="#999"
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
  <TouchableOpacity style={[s.chip, on && s.chipOn]} onPress={onPress}>
    <Text style={[s.chipText, on && s.chipTextOn]}>{on ? "✓ " : ""}{label}</Text>
  </TouchableOpacity>
);

/* ---------------------------- offer card ---------------------------- */
function OfferCard({ o, fav, onPress, onFav }) {
  return (
    <Pressable style={s.card} onPress={onPress}>
      <View style={s.thumbWrap}>
        {o.image_url
          ? <Image source={imgSource(o.image_url)} style={s.thumb} contentFit="cover" cachePolicy="memory-disk" transition={150} />
          : <View style={[s.thumb, s.thumbEmpty]}><Text style={s.thumbInitial}>{(o.merchant || "?")[0]}</Text></View>}
        {o._soon && (
          <View style={s.soon}><Text style={s.soonText}>
            {o._days === 0 ? "Last day" : o._days === 1 ? "1 day left" : `${o._days} days left`}
          </Text></View>
        )}
        {!!o._d && <View style={s.badge}><Text style={s.badgeText} numberOfLines={1}>{o._d}</Text></View>}
        <TouchableOpacity style={[s.fav, fav && s.favOn]} onPress={onFav}>
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
  safe: { flex: 1, backgroundColor: "#f6f6f8" },
  hero: { backgroundColor: "#2a1608", padding: 20, paddingTop: 42, paddingBottom: 26 },
  eyebrow: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start",
    backgroundColor: "rgba(255,255,255,0.12)", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4, marginBottom: 12 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: "#7CFC9B" },
  eyebrowText: { color: "#ffd9b8", fontSize: 10, fontWeight: "700", letterSpacing: 2 },
  h1: { color: "#fff", fontSize: 30, fontWeight: "800", letterSpacing: -0.5 },
  heroSub: { color: "rgba(255,255,255,0.85)", marginTop: 8, fontSize: 13, lineHeight: 19 },
  statsRow: { flexDirection: "row", gap: 8, marginTop: 16 },
  stat: { flexDirection: "row", alignItems: "baseline", gap: 5,
    backgroundColor: "rgba(255,255,255,0.10)", borderRadius: 10, paddingHorizontal: 12, paddingVertical: 7 },
  statN: { color: "#fff", fontWeight: "800", fontSize: 16 },
  statT: { color: "#ffe4cd", fontSize: 11 },

  label: { fontSize: 10, fontWeight: "700", color: "#8a8f98", letterSpacing: 1.5, marginTop: 16, marginLeft: 16, marginBottom: 6 },
  chipRow: { paddingHorizontal: 16, gap: 8 },
  chip: { borderWidth: 1, borderColor: "#e0e2e6", backgroundColor: "#fff", borderRadius: 999,
    paddingHorizontal: 14, paddingVertical: 8 },
  chipOn: { backgroundColor: ACCENT, borderColor: ACCENT },
  chipText: { fontSize: 12.5, color: "#333" },
  chipTextOn: { color: "#fff", fontWeight: "700" },
  search: { marginHorizontal: 16, marginTop: 14, marginBottom: 10, backgroundColor: "#fff",
    borderWidth: 1, borderColor: "#e0e2e6", borderRadius: 12, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14 },
  count: { color: "#777", fontSize: 12, margin: 16, marginBottom: 8 },
  empty: { textAlign: "center", color: "#888", marginTop: 48 },

  card: { backgroundColor: "#fff", borderRadius: 16, marginHorizontal: 16, marginBottom: 14,
    overflow: "hidden", elevation: 2, shadowColor: "#000", shadowOpacity: 0.07, shadowRadius: 8, shadowOffset: { width: 0, height: 3 } },
  thumbWrap: { position: "relative" },
  thumb: { width: "100%", aspectRatio: 16 / 9, backgroundColor: "#fdeadd" },
  thumbEmpty: { alignItems: "center", justifyContent: "center" },
  thumbInitial: { fontSize: 40, fontWeight: "800", color: ACCENT, opacity: 0.5 },
  badge: { position: "absolute", left: 10, bottom: 10, backgroundColor: ACCENT,
    borderRadius: 8, paddingHorizontal: 9, paddingVertical: 4, maxWidth: "70%" },
  badgeText: { color: "#fff", fontSize: 11.5, fontWeight: "700" },
  soon: { position: "absolute", left: 10, top: 10, backgroundColor: "#d12f2f",
    borderRadius: 7, paddingHorizontal: 8, paddingVertical: 3 },
  soonText: { color: "#fff", fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
  fav: { position: "absolute", right: 10, top: 10, width: 32, height: 32, borderRadius: 16,
    backgroundColor: "rgba(0,0,0,0.45)", alignItems: "center", justifyContent: "center" },
  favOn: { backgroundColor: ACCENT },
  cardBody: { padding: 12 },
  merchant: { fontSize: 15, fontWeight: "700", color: "#1a1d21" },
  desc: { fontSize: 12, color: "#6b7280", marginTop: 3, lineHeight: 17 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 9 },
  tag: { fontSize: 10, fontWeight: "600", color: "#6b7280", backgroundColor: "#f1f2f4",
    borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3, overflow: "hidden" },
  tagBank: { color: ACCENT, backgroundColor: "#fdeadd" },

  modalBg: { flex: 1, backgroundColor: "rgba(0,0,0,0.55)", justifyContent: "flex-end" },
  // Fixed pixel height: percentage heights around a ScrollView break
  // scrolling on Android, so give the sheet a definite size.
  modal: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20,
    height: Math.round(Dimensions.get("window").height * 0.85), overflow: "hidden" },
  modalImg: { width: "100%", aspectRatio: 16 / 9 },
  modalTitle: { fontSize: 20, fontWeight: "800", color: "#1a1d21" },
  modalDiscount: { color: ACCENT, fontWeight: "800", fontSize: 15, marginTop: 4 },
  modalDesc: { fontSize: 13.5, color: "#333", lineHeight: 20, marginTop: 10 },
  section: { marginTop: 14, borderTopWidth: 1, borderTopColor: "#eee", paddingTop: 10 },
  sectionTitle: { fontWeight: "700", fontSize: 13.5, color: "#1a1d21" },
  sectionBody: { fontSize: 12.5, color: "#6b7280", lineHeight: 19, marginTop: 8 },
  link: { color: ACCENT, fontWeight: "700", marginTop: 16, fontSize: 13.5 },
  close: { position: "absolute", top: 12, right: 12, width: 32, height: 32, borderRadius: 16,
    backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center" },
});
