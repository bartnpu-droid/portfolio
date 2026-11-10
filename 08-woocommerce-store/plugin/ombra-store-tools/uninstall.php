<?php
/**
 * Removes the plugin's settings when it is deleted from the Plugins screen.
 * Product fields and order gift notes stay: they are store data.
 *
 * @package Ombra\StoreTools
 */

defined( 'WP_UNINSTALL_PLUGIN' ) || exit;

$ombra_options = array(
	'ombra_fsb_enabled',
	'ombra_fsb_goal_source',
	'ombra_fsb_goal',
	'ombra_fsb_message_progress',
	'ombra_fsb_message_done',
	'ombra_fsb_message_empty',
	'ombra_fsb_bar_color',
	'ombra_fsb_hide_paid',
	'ombra_gift_enabled',
	'ombra_gift_note_length',
	'ombra_badges_sale',
);
foreach ( $ombra_options as $ombra_option ) {
	delete_option( $ombra_option );
}
