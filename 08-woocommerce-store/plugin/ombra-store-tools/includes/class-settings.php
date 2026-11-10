<?php
/**
 * WooCommerce → Settings → Ombra tab.
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

defined( 'ABSPATH' ) || exit;

/**
 * All plugin options live in one settings tab, built with the WooCommerce settings API.
 */
class Settings {

	const TAB = 'ombra';

	/**
	 * Default values for every option.
	 *
	 * @var array<string, string>
	 */
	const DEFAULTS = array(
		'ombra_fsb_enabled'          => 'yes',
		'ombra_fsb_goal_source'      => 'method',
		'ombra_fsb_goal'             => '75',
		'ombra_fsb_message_progress' => "You're [amount] away from free shipping",
		'ombra_fsb_message_done'     => 'Your order ships free',
		'ombra_fsb_message_empty'    => 'Free shipping on orders over [goal]',
		'ombra_fsb_bar_color'        => '#a24e2b',
		'ombra_fsb_hide_paid'        => 'yes',
		'ombra_gift_enabled'         => 'yes',
		'ombra_gift_note_length'     => '160',
		'ombra_badges_sale'          => 'yes',
	);

	/**
	 * Hooks.
	 */
	public static function init() {
		add_filter( 'woocommerce_settings_tabs_array', array( __CLASS__, 'add_tab' ), 50 );
		add_action( 'woocommerce_settings_tabs_' . self::TAB, array( __CLASS__, 'output' ) );
		add_action( 'woocommerce_update_options_' . self::TAB, array( __CLASS__, 'save' ) );
	}

	/**
	 * Read an option with its default.
	 *
	 * @param string $key Option name.
	 * @return string
	 */
	public static function get( $key ) {
		$default = self::DEFAULTS[ $key ] ?? '';
		$value   = get_option( $key, $default );
		return is_string( $value ) ? $value : $default;
	}

	/**
	 * Whether a yes/no option is on.
	 *
	 * @param string $key Option name.
	 * @return bool
	 */
	public static function is_on( $key ) {
		return 'yes' === self::get( $key );
	}

	/**
	 * Add the tab.
	 *
	 * @param array $tabs Settings tabs.
	 * @return array
	 */
	public static function add_tab( $tabs ) {
		$tabs[ self::TAB ] = __( 'Ombra', 'ombra-store-tools' );
		return $tabs;
	}

	/**
	 * Print the fields.
	 */
	public static function output() {
		woocommerce_admin_fields( self::fields() );
	}

	/**
	 * Save the fields.
	 */
	public static function save() {
		woocommerce_update_options( self::fields() );
	}

	/**
	 * Field definitions.
	 *
	 * @return array
	 */
	public static function fields() {
		$method_note = Free_Shipping::method_goal_note();

		return array(
			array(
				'title' => __( 'Free shipping bar', 'ombra-store-tools' ),
				'type'  => 'title',
				'desc'  => __( 'A progress bar towards free shipping. It updates after every change to the cart: in the Cart and Checkout blocks, in the mini-cart drawer and anywhere the "Free shipping progress" block is placed (the theme puts it in the announcement bar and on product pages).', 'ombra-store-tools' ),
				'id'    => 'ombra_fsb',
			),
			array(
				'title'   => __( 'Show the bar', 'ombra-store-tools' ),
				'id'      => 'ombra_fsb_enabled',
				'type'    => 'checkbox',
				'default' => self::DEFAULTS['ombra_fsb_enabled'],
			),
			array(
				'title'    => __( 'Free shipping goal', 'ombra-store-tools' ),
				'id'       => 'ombra_fsb_goal_source',
				'type'     => 'radio',
				'default'  => self::DEFAULTS['ombra_fsb_goal_source'],
				'options'  => array(
					'method' => __( 'Use the minimum order amount of the "Free shipping" method in the customer\'s shipping zone', 'ombra-store-tools' ),
					'custom' => __( 'Use the amount below', 'ombra-store-tools' ),
				),
				'desc'     => $method_note,
				'desc_tip' => false,
			),
			array(
				'title'             => __( 'Amount', 'ombra-store-tools' ),
				'id'                => 'ombra_fsb_goal',
				'type'              => 'number',
				'default'           => self::DEFAULTS['ombra_fsb_goal'],
				'custom_attributes' => array(
					'min'  => '0',
					'step' => '0.01',
				),
				'desc'              => __( 'Used when the goal is set to "the amount below", and as a fallback when no zone has a Free shipping method.', 'ombra-store-tools' ),
			),
			array(
				'title'   => __( 'Message on the way', 'ombra-store-tools' ),
				'id'      => 'ombra_fsb_message_progress',
				'type'    => 'text',
				'default' => self::DEFAULTS['ombra_fsb_message_progress'],
				'desc'    => __( '[amount] is replaced with the amount left.', 'ombra-store-tools' ),
				'css'     => 'min-width: 420px;',
			),
			array(
				'title'   => __( 'Message when reached', 'ombra-store-tools' ),
				'id'      => 'ombra_fsb_message_done',
				'type'    => 'text',
				'default' => self::DEFAULTS['ombra_fsb_message_done'],
				'css'     => 'min-width: 420px;',
			),
			array(
				'title'   => __( 'Message with an empty cart', 'ombra-store-tools' ),
				'id'      => 'ombra_fsb_message_empty',
				'type'    => 'text',
				'default' => self::DEFAULTS['ombra_fsb_message_empty'],
				'desc'    => __( 'Shown in the announcement bar before anything is added. [goal] is replaced with the goal.', 'ombra-store-tools' ),
				'css'     => 'min-width: 420px;',
			),
			array(
				'title'   => __( 'Bar colour', 'ombra-store-tools' ),
				'id'      => 'ombra_fsb_bar_color',
				'type'    => 'color',
				'default' => self::DEFAULTS['ombra_fsb_bar_color'],
				'css'     => 'width: 7em;',
			),
			array(
				'title'   => __( 'When an order qualifies', 'ombra-store-tools' ),
				'desc'    => __( 'Offer only free shipping (and local pickup), so nobody pays for shipping by mistake', 'ombra-store-tools' ),
				'id'      => 'ombra_fsb_hide_paid',
				'type'    => 'checkbox',
				'default' => self::DEFAULTS['ombra_fsb_hide_paid'],
			),
			array(
				'type' => 'sectionend',
				'id'   => 'ombra_fsb',
			),
			array(
				'title' => __( 'Gift options at checkout', 'ombra-store-tools' ),
				'type'  => 'title',
				'desc'  => __( 'Adds "This order is a gift" and a gift note to the Checkout block (Additional Checkout Fields API). The note only appears when the box is ticked, and it is saved with the order, shown in the order screen, in emails and in the orders list.', 'ombra-store-tools' ),
				'id'    => 'ombra_gift',
			),
			array(
				'title'   => __( 'Gift options', 'ombra-store-tools' ),
				'desc'    => __( 'Show the gift options at checkout', 'ombra-store-tools' ),
				'id'      => 'ombra_gift_enabled',
				'type'    => 'checkbox',
				'default' => self::DEFAULTS['ombra_gift_enabled'],
			),
			array(
				'title'             => __( 'Longest gift note', 'ombra-store-tools' ),
				'id'                => 'ombra_gift_note_length',
				'type'              => 'number',
				'default'           => self::DEFAULTS['ombra_gift_note_length'],
				'custom_attributes' => array(
					'min'  => '20',
					'max'  => '500',
					'step' => '1',
				),
				'desc'              => __( 'Characters. Longer notes are stopped at checkout with a clear message.', 'ombra-store-tools' ),
			),
			array(
				'type' => 'sectionend',
				'id'   => 'ombra_gift',
			),
			array(
				'title' => __( 'Product badges', 'ombra-store-tools' ),
				'type'  => 'title',
				'desc'  => __( 'Choose a badge (New, Bestseller, Limited edition, Back in stock) on each product, in the "Ombra details" tab of the product data box.', 'ombra-store-tools' ),
				'id'    => 'ombra_badges',
			),
			array(
				'title'   => __( 'Sale badge', 'ombra-store-tools' ),
				'desc'    => __( 'Show "Sale" on discounted products that have no other badge', 'ombra-store-tools' ),
				'id'      => 'ombra_badges_sale',
				'type'    => 'checkbox',
				'default' => self::DEFAULTS['ombra_badges_sale'],
			),
			array(
				'type' => 'sectionend',
				'id'   => 'ombra_badges',
			),
		);
	}
}
