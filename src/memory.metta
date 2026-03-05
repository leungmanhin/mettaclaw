;Configured at runtime memory and history in amount of characters:
(= (maxMemory) (empty))
(= (maxRecallItems) (empty))
(= (maxHistory) (empty))

(= (initMemory)
   (progn (println! "Initializing memory")
          (configure maxMemory 2000)
          (configure maxRecallItems 5)
          (configure maxHistory 5000)))

(= (getPrompt)
   (read-file (library mettaclaw ./memory/prompt.txt)))

(= (getMemory)
   (let $ret (read-file (library mettaclaw ./memory/STM.metta))
        (last_chars $ret (maxMemory))))

(= (getHistory)
   (let $ret (read-file (library mettaclaw ./memory/history.metta))
        (last_chars $ret (maxHistory))))

(= (addToHistory $lastmessage $response $sexpr)
   (appendToHistory ((get_time_as_string) (newline) $lastmessage (newline) $response)))

(= (appendToHistory $addition)
   (append-file (library mettaclaw ./memory/history.metta) (swrite $addition)))

(= (remember $str)
   (progn (append-file (library mettaclaw ./memory/STM.metta) (repr ((get_time_as_string) $str)))
          (let $embedding (useGPTEmbedding (string-safe $str))
               (append-file (library mettaclaw ./memory/LTM.metta) (repr ((get_time_as_string) $str $embedding))))))

(= (query $str)
   (let* (($embedding (useGPTEmbedding (string-safe $str)))
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
