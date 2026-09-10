import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import AsyncStorage from "@react-native-async-storage/async-storage";

const en = {
  login: "Login with Phone", phone: "Phone Number", sendOtp: "Send OTP", otp: "Enter OTP", verify: "Verify", home: "Home", cases: "Cases", map: "Map", profile: "Profile",
  newInspection: "New Inspection", myCases: "My Cases", toServe: "Notices to serve", executionDue: "Execution due", inbox: "Inbox", drafts: "Drafts", overdue: "Overdue",
  quickActions: "Quick Actions", todaysSummary: "Today's Summary", locationStatus: "Location Status", gpsAccuracy: "GPS Accuracy", good: "GOOD", poor: "POOR", offlineQueue: "Offline queue",
  sync: "Sync now", logout: "Logout", language: "Language", darkMode: "Dark Mode", pid: "Property ID (PID)", fetch: "Fetch", address: "Address", violations: "Violations", evidence: "Evidence",
  takePhoto: "Take photo", recordVideo: "Record video", submit: "Submit to AE", saveDraft: "Save draft", description: "Observations", recordDelivery: "Record delivery", uploadReply: "Upload reply",
  recordExecution: "Record demolition / sealing", sealedPremises: "Sealed", stopWork: "Stop-work", governmentLand: "Government land", private: "Private land",
};
const hi: typeof en = {
  login: "फ़ोन से लॉगिन", phone: "मोबाइल नंबर", sendOtp: "ओटीपी भेजें", otp: "ओटीपी दर्ज करें", verify: "सत्यापित करें", home: "होम", cases: "प्रकरण", map: "मानचित्र", profile: "प्रोफ़ाइल",
  newInspection: "नया निरीक्षण", myCases: "मेरे प्रकरण", toServe: "तामील हेतु नोटिस", executionDue: "निष्पादन देय", inbox: "इनबॉक्स", drafts: "प्रारूप", overdue: "विलंबित",
  quickActions: "त्वरित कार्य", todaysSummary: "आज का सारांश", locationStatus: "लोकेशन स्थिति", gpsAccuracy: "GPS सटीकता", good: "अच्छी", poor: "कमज़ोर", offlineQueue: "ऑफ़लाइन कतार",
  sync: "अभी सिंक करें", logout: "लॉग आउट", language: "भाषा", darkMode: "डार्क मोड", pid: "प्रॉपर्टी आईडी (PID)", fetch: "प्राप्त करें", address: "पता", violations: "उल्लंघन", evidence: "साक्ष्य",
  takePhoto: "फ़ोटो लें", recordVideo: "वीडियो रिकॉर्ड करें", submit: "ए.ई. को भेजें", saveDraft: "प्रारूप सहेजें", description: "निरीक्षण टिप्पणी", recordDelivery: "तामील दर्ज करें", uploadReply: "उत्तर अपलोड करें",
  recordExecution: "ध्वस्तीकरण / सीलिंग दर्ज करें", sealedPremises: "सील", stopWork: "कार्य-रोक", governmentLand: "सरकारी भूमि", private: "निजी भूमि",
};
i18n.use(initReactI18next).init({ resources: { en: { translation: en }, hi: { translation: hi } }, lng: "en", fallbackLng: "en", interpolation: { escapeValue: false } });
AsyncStorage.getItem("lang").then((l) => { if (l) i18n.changeLanguage(l); });
export const setLang = async (l: string) => { await AsyncStorage.setItem("lang", l); i18n.changeLanguage(l); };
export default i18n;
