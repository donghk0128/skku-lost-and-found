import AccountPosts from "@/components/account-posts";
import { useCallback } from "react";
import { useFocusEffect } from "expo-router";
import { newVisitId, trackEvent } from "@/lib/event-logging";

export default function MyPosts() {
  useFocusEffect(useCallback(() => {
    trackEvent({ event_type: "screen_view", screen: "my_posts", visit_id: newVisitId() });
  }, []));
  return <AccountPosts />;
}
