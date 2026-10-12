import {
  useEffect,
  useRef,
  useState,
} from "react";

import api from "../api";


const POLL_INTERVAL_MS = 20000;


function useTaskNotifications() {

  const [tasks, setTasks] =
    useState([]);

  const [newTaskCount, setNewTaskCount] =
    useState(0);

  const [lastNewTask, setLastNewTask] =
    useState(null);

  const initialized =
    useRef(false);

  const knownTaskIds =
    useRef(
      new Set()
    );


  useEffect(() => {

    let intervalId = null;

    let isMounted = true;


    async function requestBrowserPermission() {

      if (
        !("Notification" in window)
      ) {
        return;
      }


      if (
        Notification.permission ===
        "default"
      ) {

        try {

          await Notification.requestPermission();

        } catch (error) {

          console.error(
            "Notification permission error:",
            error
          );
        }
      }
    }


    function playNotificationSound() {

      try {

        const audio =
          new Audio(
            "/notification.mp3"
          );

        audio.volume = 0.65;

        audio.play().catch(
          () => {}
        );

      } catch (error) {

        console.error(
          "Notification sound error:",
          error
        );
      }
    }


    function showBrowserNotification(
      task
    ) {

      if (
        !("Notification" in window)
      ) {
        return;
      }


      if (
        Notification.permission !==
        "granted"
      ) {
        return;
      }


      const routeName =
        task.route?.name ||
        "مسیر جدید";


      const type =
        task.change?.type ||
        "تغییر جدید";


      const notification =
        new Notification(
          "Aryak Tour Monitor",
          {
            body:
              `${routeName} - ${type}`,

            icon:
              "/aryak-logo.png",

            badge:
              "/aryak-logo.png",

            tag:
              `task-${task.id}`,
          }
        );


      notification.onclick =
        () => {

          window.focus();

          window.location.href =
            `/tasks/${task.id}`;
        };
    }


    async function loadTasks() {

      try {

        const response =
          await api.get(
            "/panel/my-tasks"
          );


        const currentTasks =
          response.data ||
          [];


        if (!isMounted) {
          return;
        }


        setTasks(
          currentTasks
        );


        const visibleNewTasks =
          currentTasks.filter(
            (task) =>
              task.status ===
              "NEW"
          );


        setNewTaskCount(
          visibleNewTasks.length
        );


        // =================================================
        // FIRST LOAD
        // =================================================
        //
        // On first load we only remember existing task IDs.
        // We do NOT fire sound/browser notification for
        // tasks that already existed before page was opened.
        //

        if (!initialized.current) {

          currentTasks.forEach(
            (task) => {

              knownTaskIds.current.add(
                task.id
              );
            }
          );


          initialized.current =
            true;

          return;
        }


        // =================================================
        // DETECT NEW TASKS
        // =================================================

        const unseenTasks =
          currentTasks.filter(
            (task) => {

              return (
                task.status ===
                  "NEW" &&

                !knownTaskIds.current.has(
                  task.id
                )
              );
            }
          );


        // Remember every task
        currentTasks.forEach(
          (task) => {

            knownTaskIds.current.add(
              task.id
            );
          }
        );


        if (
          unseenTasks.length === 0
        ) {
          return;
        }


        const newestTask =
          unseenTasks[0];


        setLastNewTask(
          newestTask
        );


        playNotificationSound();

        showBrowserNotification(
          newestTask
        );


      } catch (error) {

        console.error(
          "Task notification polling error:",
          error
        );
      }
    }


    requestBrowserPermission();

    loadTasks();


    intervalId =
      setInterval(
        loadTasks,
        POLL_INTERVAL_MS
      );


    return () => {

      isMounted = false;

      if (intervalId) {

        clearInterval(
          intervalId
        );
      }

    };

  }, []);


  function clearPopup() {

    setLastNewTask(
      null
    );
  }


  return {

    tasks,

    newTaskCount,

    lastNewTask,

    clearPopup,
  };
}


export default useTaskNotifications;