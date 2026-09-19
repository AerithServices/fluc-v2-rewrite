INSERT INTO punishments(
    punishment_id,
    user_id,
    target_user_id,
    action_id,
    executed_action_id,
    done_at
) VALUES(%s, %s, %s, %s, %s, %s);
