;Configured at runtime memory and history in amount of characters:
(= (maxFeedback) (empty))
(= (maxRecallItems) (empty))
(= (maxHistory) (empty))

(= (initMemory)
   (progn (println! "Initializing memory")
          (configure maxFeedback 50000)
          (configure maxRecallItems 20)
          (configure maxHistory 30000)))

(= (getPrompt)
   (read-file (library mettaclaw ./memory/prompt.txt)))

(= (getSemanticParsingPrompt)
   (read-file (library mettaclaw ./memory/semantic_parsing_prompt.txt)))

(= (getHistory)
   (let $ret (read-file (library mettaclaw ./memory/history.metta))
        (last_chars $ret (maxHistory))))

(= (addToHistory $lastmessage $response $sexpr $msgnew)
   (if $msgnew
       (if (== (get-state &error) ())
           (appendToHistory ((get_time_as_string) (newline) "HUMAN_MESSAGE: " $lastmessage (newline) $response (newline)))
           (appendToHistory ((get_time_as_string) (newline) "HUMAN_MESSAGE: " $lastmessage (newline) $response (newline) ERROR_FEEDBACK: (get-state &error))))
       (if (== (get-state &error) ())
           (appendToHistory ((get_time_as_string) (newline) $response (newline)))
           (appendToHistory ((get_time_as_string) (newline) $response (newline) ERROR_FEEDBACK: (get-state &error))))))

(= (appendToHistory $addition)
   (append-file (library mettaclaw ./memory/history.metta) (swrite $addition)))

 (= (remember $str)
    (progn (append-file (library mettaclaw ./memory/STM.metta) (repr ((get_time_as_string) $str)))
           (let $embedding (useOpenRouterEmbedding "openai/text-embedding-3-large" (string-safe $str))
                (append-file (library mettaclaw ./memory/LTM.metta) (repr ((get_time_as_string) $str $embedding))))))

(= (query $str)
   (let* (($embedding (useOpenRouterEmbedding "openai/text-embedding-3-large" (string-safe $str)))
          ($text (read-file (library mettaclaw ./memory/LTM.metta)))
          ($atoms (parse (string_concat (string_concat "(" $text) ")"))))
        (progn (let $sorted (msort (collapse (for ($date $atom $vector) $atoms ((cosine $vector $embedding) $date $atom))))
                    (let $u (collapse (for ($sim $date $atom) (take (maxRecallItems) (reverse $sorted))
                                   ($date $atom)))
                                   (repr $u))))))

(= (remember $str)
   (let $sp-rtn (py-call (semantic_parsing.nl2pln_to_file
                       (read-file (library mettaclaw ./memory/semantic_parsing_prompt.txt))
                       (string-safe (py-str ("HISTORY: " (getHistory) (newline) "CURRENT TIME: " (get_time_as_string))))
                       $str
                       "parsing"))
        (append-file (library mettaclaw ./memory/SPM.metta) $sp-rtn)))

(= (query $str)
   (let $sp-rtn (py-call (semantic_parsing.nl2pln_to_chainer
                        (read-file (library mettaclaw ./memory/semantic_querying_prompt.txt))
                        (string-safe (py-str ("HISTORY: " (getHistory) (newline) "CURRENT TIME: " (get_time_as_string))))
                        $str
                        "querying"))
        (py-call (chaining.chain_queries $sp-rtn))))
