import AccountPosts from "@/components/account-posts";
import { useEffect, useRef } from "react";
import { newVisitId, trackEvent } from "@/lib/event-logging";

export default function MyPosts() {
  const visitId = useRef(newVisitId());
  const viewed = useRef(false);
  useEffect(() => {
    if (!viewed.current) {
      viewed.current = true;
      trackEvent({ event_type: "screen_view", screen: "my_posts", visit_id: visitId.current });
    }
  }, []);
  return <AccountPosts />;
}
