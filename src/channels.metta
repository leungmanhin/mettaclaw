;configured at runtime:
(= (IRC_channel) (empty))
(= (IRC_server) (empty))
(= (IRC_port) (empty))
(= (IRC_user) (empty))
(= (commchannel) (empty))
(= (MM_URL) (empty))
(= (MM_CHANNEL_ID) (empty))
(= (MM_BOT_TOKEN) (empty))
(= (TERMINAL_PORT) (empty))

;Connect all the channels:
(= (initChannels)
   (progn (println! "Initializing channels")
          (configure commchannel terminal)
          (if (== (commchannel) irc)
              (progn (configure IRC_channel ##metta)
                     (configure IRC_server "irc.quakenet.org")
                     (configure IRC_port 6667)
                     (configure IRC_user maxbotnick-mh)
                     (py-call (irc.start_irc (IRC_channel) (IRC_server) (IRC_port) (IRC_user))))
              (if (== (commchannel) mattermost)
                  (progn (configure MM_URL "https://chat.singularitynet.io")
                         (configure MM_CHANNEL_ID "8fjrmabjx7gupy7e5kjznpt5qh")
                         (configure MM_BOT_TOKEN "")
                         (py-call (mattermost.start_mattermost (MM_URL) (MM_CHANNEL_ID) (MM_BOT_TOKEN))))
                  (progn (configure TERMINAL_PORT 3333)
                         (py-call (terminal.start_terminal (TERMINAL_PORT))))))))




;Receive the latest user message considering all communication channels:
(= (receive)
   (if (== (commchannel) irc)
       (py-call (irc.getLastMessage))
       (if (== (commchannel) mattermost)
           (py-call (mattermost.getLastMessage))
           (py-call (terminal.getLastMessage)))))

;Send a message to all communication channels:
(= (send $msg)
   (let $safemsg (string-replace $msg  "\n" "\\n")
        (if (== (commchannel) irc)
            (let $temp (cut) (py-call (irc.send_message $safemsg)))
            (if (== (commchannel) mattermost)
                (let $temp (cut) (py-call (mattermost.send_message $safemsg)))
                (let $temp (cut) (py-call (terminal.send_message $safemsg)))))))

;Search the internet for some information:
(= (search $msg)
   (py-call (websearch.search $msg)))
