<?php
/**
 * Gift options in the Checkout block, through the Additional Checkout Fields API.
 *
 * WooCommerce stores, validates and displays these fields itself (order screen, emails,
 * order confirmation). This class registers them and adds a "Gift" column to the orders list.
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

defined( 'ABSPATH' ) || exit;

/**
 * Gift options.
 */
class Gift_Options {

	const FIELD_GIFT = 'ombra/is-gift';
	const FIELD_NOTE = 'ombra/gift-note';

	/**
	 * WooCommerce saves "order" location fields as order meta with this prefix.
	 */
	const META_PREFIX = '_wc_other/';

	/**
	 * Hooks.
	 */
	public static function init() {
		if ( ! Settings::is_on( 'ombra_gift_enabled' ) ) {
			return;
		}
		add_action( 'woocommerce_init', array( __CLASS__, 'register_fields' ) );

		// Orders list column, for both order storage modes.
		add_filter( 'manage_woocommerce_page_wc-orders_columns', array( __CLASS__, 'add_column' ) );
		add_action( 'manage_woocommerce_page_wc-orders_custom_column', array( __CLASS__, 'column' ), 10, 2 );
		add_filter( 'manage_edit-shop_order_columns', array( __CLASS__, 'add_column' ) );
		add_action( 'manage_shop_order_posts_custom_column', array( __CLASS__, 'column' ), 10, 2 );
	}

	/**
	 * Register the two fields in the "order" location of the Checkout block.
	 */
	public static function register_fields() {
		if ( ! function_exists( 'woocommerce_register_additional_checkout_field' ) ) {
			return;
		}

		woocommerce_register_additional_checkout_field(
			array(
				'id'            => self::FIELD_GIFT,
				'label'         => __( 'This order is a gift: no prices in the parcel, and a handwritten card', 'ombra-store-tools' ),
				// A checkbox is optional by nature, so no "(optional)" after it.
				'optionalLabel' => __( 'This order is a gift: no prices in the parcel, and a handwritten card', 'ombra-store-tools' ),
				'location'      => 'order',
				'type'          => 'checkbox',
			)
		);

		$max = self::note_length();
		woocommerce_register_additional_checkout_field(
			array(
				'id'                => self::FIELD_NOTE,
				'label'             => __( 'Gift note for the card', 'ombra-store-tools' ),
				'optionalLabel'     => __( 'Gift note for the card (optional)', 'ombra-store-tools' ),
				'location'          => 'order',
				'type'              => 'text',
				'attributes'        => array(
					'autocomplete' => 'off',
					'maxLength'    => $max,
				),
				// Shown only when "This order is a gift" is ticked (JSON Schema rule against the checkout data).
				'hidden'            => array(
					'type'       => 'object',
					'properties' => array(
						'checkout' => array(
							'properties' => array(
								'additional_fields' => array(
									'properties' => array(
										self::FIELD_GIFT => array( 'not' => array( 'const' => true ) ),
									),
								),
							),
						),
					),
				),
				'sanitize_callback' => array( __CLASS__, 'sanitize_note' ),
				'validate_callback' => array( __CLASS__, 'validate_note' ),
			)
		);
	}

	/**
	 * Longest allowed note.
	 *
	 * @return int
	 */
	public static function note_length() {
		return max( 20, min( 500, (int) Settings::get( 'ombra_gift_note_length' ) ) );
	}

	/**
	 * Clean the note: one line of plain text.
	 *
	 * @param mixed $value Raw value.
	 * @return string
	 */
	public static function sanitize_note( $value ) {
		return trim( preg_replace( '/\s+/u', ' ', sanitize_text_field( (string) $value ) ) );
	}

	/**
	 * Stop notes that are too long, with a message the shopper understands.
	 *
	 * @param mixed $value Sanitized value.
	 * @return true|\WP_Error
	 */
	public static function validate_note( $value ) {
		$max = self::note_length();
		if ( mb_strlen( (string) $value ) > $max ) {
			return new \WP_Error(
				'ombra_gift_note_too_long',
				/* translators: %d: maximum number of characters */
				sprintf( __( 'Please keep the gift note to %d characters, so it fits on the card.', 'ombra-store-tools' ), $max )
			);
		}
		return true;
	}

	/**
	 * Add the column after the order status.
	 *
	 * @param array $columns Columns.
	 * @return array
	 */
	public static function add_column( $columns ) {
		$out = array();
		foreach ( $columns as $key => $label ) {
			$out[ $key ] = $label;
			if ( 'order_status' === $key ) {
				$out['ombra_gift'] = __( 'Gift', 'ombra-store-tools' );
			}
		}
		if ( ! isset( $out['ombra_gift'] ) ) {
			$out['ombra_gift'] = __( 'Gift', 'ombra-store-tools' );
		}
		return $out;
	}

	/**
	 * Column content: "Gift" with the note as a tooltip.
	 *
	 * @param string        $column Column key.
	 * @param int|\WC_Order $order  Order or order ID (posts table).
	 */
	public static function column( $column, $order ) {
		if ( 'ombra_gift' !== $column ) {
			return;
		}
		$order = $order instanceof \WC_Order ? $order : wc_get_order( $order );
		if ( ! $order ) {
			return;
		}
		if ( ! wc_string_to_bool( (string) $order->get_meta( self::META_PREFIX . self::FIELD_GIFT ) ) ) {
			echo '<span aria-hidden="true">–</span>';
			return;
		}
		$note = (string) $order->get_meta( self::META_PREFIX . self::FIELD_NOTE );
		printf(
			'<mark class="order-status status-processing tips" data-tip="%1$s"><span>%2$s</span></mark>',
			esc_attr( $note ? $note : __( 'No note', 'ombra-store-tools' ) ),
			esc_html__( 'Gift', 'ombra-store-tools' )
		);
	}
}
