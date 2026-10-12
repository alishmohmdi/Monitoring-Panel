import {
  useEffect,
} from "react";

import api from "../api";


const HEARTBEAT_INTERVAL_MS =
  60000;


function usePresenceHeartbeat() {

  useEffect(() => {

    const token =
      localStorage.getItem(
        "aryak_token"
      );


    if (!token) {
      return;
    }


    let intervalId = null;

    let stopped = false;


    async function sendHeartbeat() {

      if (stopped) {
        return;
      }


      try {

        await api.post(
          "/presence/heartbeat"
        );

      } catch (error) {

        console.error(
          "Presence heartbeat error:",
          error
        );
      }
    }


    // Send immediately.
    sendHeartbeat();


    intervalId =
      setInterval(
        sendHeartbeat,
        HEARTBEAT_INTERVAL_MS
      );


    return () => {

      stopped = true;

      if (intervalId) {

        clearInterval(
          intervalId
        );
      }
    };

  }, []);
}


export default usePresenceHeartbeat;