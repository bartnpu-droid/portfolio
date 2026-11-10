<?php
/**
 * "Ombra details" tab in the product data box: badge, scent notes, burn time, wax.
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

defined( 'ABSPATH' ) || exit;

/**
 * Product fields.
 */
class Product_Fields {

	/**
	 * Meta keys for the text fields.
	 *
	 * @var array<string, string>
	 */
	const NOTE_KEYS = array(
		'top'   => '_ombra_notes_top',
		'heart' => '_ombra_notes_heart',
		'base'  => '_ombra_notes_base',
		'burn'  => '_ombra_burn_time',
		'wax'   => '_ombra_wax',
	);

	const BADGE_KEY = '_ombra_badge';

	/**
	 * Hooks.
	 */
	public static function init() {
		add_filter( 'woocommerce_product_data_tabs', array( __CLASS__, 'add_tab' ) );
		add_action( 'woocommerce_product_data_panels', array( __CLASS__, 'panel' ) );
		add_action( 'woocommerce_admin_process_product_object', array( __CLASS__, 'save' ) );
		add_action( 'admin_head', array( __CLASS__, 'tab_icon' ) );
	}

	/**
	 * Badge choices.
	 *
	 * @return array<string, string>
	 */
	public static function badges() {
		/**
		 * Filters the badge choices.
		 *
		 * @param array<string, string> $badges Key => label.
		 */
		return apply_filters(
			'ombra_store_tools_badges',
			array(
				'new'        => __( 'New', 'ombra-store-tools' ),
				'bestseller' => __( 'Bestseller', 'ombra-store-tools' ),
				'limited'    => __( 'Limited edition', 'ombra-store-tools' ),
				'back'       => __( 'Back in stock', 'ombra-store-tools' ),
			)
		);
	}

	/**
	 * The badge to show for a product, if any.
	 *
	 * @param int $product_id Product ID.
	 * @return array{key: string, label: string}|null
	 */
	public static function badge( $product_id ) {
		$product = wc_get_product( $product_id );
		if ( ! $product ) {
			return null;
		}
		$key    = (string) $product->get_meta( self::BADGE_KEY );
		$badges = self::badges();
		if ( isset( $badges[ $key ] ) ) {
			return array(
				'key'   => $key,
				'label' => $badges[ $key ],
			);
		}
		if ( Settings::is_on( 'ombra_badges_sale' ) && $product->is_on_sale() ) {
			return array(
				'key'   => 'sale',
				'label' => __( 'Sale', 'ombra-store-tools' ),
			);
		}
		return null;
	}

	/**
	 * Scent notes and burn details of a product.
	 *
	 * @param int $product_id Product ID.
	 * @return array<string, string>
	 */
	public static function notes( $product_id ) {
		$product = wc_get_product( $product_id );
		if ( ! $product ) {
			return array();
		}
		$notes = array();
		foreach ( self::NOTE_KEYS as $key => $meta ) {
			$value = trim( (string) $product->get_meta( $meta ) );
			if ( '' !== $value ) {
				$notes[ $key ] = $value;
			}
		}
		return $notes;
	}

	/**
	 * Add the tab.
	 *
	 * @param array $tabs Product data tabs.
	 * @return array
	 */
	public static function add_tab( $tabs ) {
		$tabs['ombra'] = array(
			'label'    => __( 'Ombra details', 'ombra-store-tools' ),
			'target'   => 'ombra_product_data',
			'class'    => array(),
			'priority' => 65,
		);
		return $tabs;
	}

	/**
	 * Tab content.
	 */
	public static function panel() {
		global $product_object;
		?>
		<div id="ombra_product_data" class="panel woocommerce_options_panel hidden">
			<div class="options_group">
				<?php
				woocommerce_wp_select(
					array(
						'id'          => self::BADGE_KEY,
						'label'       => __( 'Badge', 'ombra-store-tools' ),
						'options'     => array( '' => __( 'No badge', 'ombra-store-tools' ) ) + self::badges(),
						'value'       => $product_object ? $product_object->get_meta( self::BADGE_KEY ) : '',
						'desc_tip'    => true,
						'description' => __( 'Shown on the product image in the shop and on the product page.', 'ombra-store-tools' ),
					)
				);
				?>
			</div>
			<div class="options_group">
				<?php
				$fields = array(
					'top'   => array( __( 'Top notes', 'ombra-store-tools' ), __( 'e.g. Green fig leaf', 'ombra-store-tools' ) ),
					'heart' => array( __( 'Heart notes', 'ombra-store-tools' ), __( 'e.g. Fig milk, violet', 'ombra-store-tools' ) ),
					'base'  => array( __( 'Base notes', 'ombra-store-tools' ), __( 'e.g. Cedarwood, vetiver', 'ombra-store-tools' ) ),
					'burn'  => array( __( 'Burn time', 'ombra-store-tools' ), __( 'e.g. 45 hours (200 g), 80 hours (400 g)', 'ombra-store-tools' ) ),
					'wax'   => array( __( 'Made with', 'ombra-store-tools' ), __( 'e.g. Coconut-soy wax, cotton wick', 'ombra-store-tools' ) ),
				);
				foreach ( $fields as $key => $field ) {
					woocommerce_wp_text_input(
						array(
							'id'          => self::NOTE_KEYS[ $key ],
							'label'       => $field[0],
							'placeholder' => $field[1],
							'value'       => $product_object ? $product_object->get_meta( self::NOTE_KEYS[ $key ] ) : '',
						)
					);
				}
				?>
				<p class="form-field"><span class="description"><?php esc_html_e( 'Shown by the "Scent notes" block: as a list on the product page and as one line (top and base notes) on product cards.', 'ombra-store-tools' ); ?></span></p>
			</div>
		</div>
		<?php
	}

	/**
	 * Save the fields with the product (works with the product CRUD, so HPOS-safe and cache-friendly).
	 *
	 * @param \WC_Product $product Product being saved.
	 */
	public static function save( $product ) {
		// phpcs:disable WordPress.Security.NonceVerification.Missing -- WooCommerce checks the nonce before this hook runs.
		$badge = isset( $_POST[ self::BADGE_KEY ] ) ? sanitize_key( wp_unslash( $_POST[ self::BADGE_KEY ] ) ) : '';
		$product->update_meta_data( self::BADGE_KEY, array_key_exists( $badge, self::badges() ) ? $badge : '' );

		foreach ( self::NOTE_KEYS as $meta ) {
			$value = isset( $_POST[ $meta ] ) ? sanitize_text_field( wp_unslash( $_POST[ $meta ] ) ) : '';
			$product->update_meta_data( $meta, $value );
		}
		// phpcs:enable
	}

	/**
	 * Icon for the tab, in the style of the built-in tabs.
	 */
	public static function tab_icon() {
		$screen = get_current_screen();
		if ( ! $screen || 'product' !== $screen->id ) {
			return;
		}
		echo '<style>#woocommerce-product-data ul.wc-tabs li.ombra_options a::before{content:"\f511";font-family:dashicons;}</style>';
	}
}
